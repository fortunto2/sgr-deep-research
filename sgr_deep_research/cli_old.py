"""CLI интерфейс для SGR Deep Research агентов."""

import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Type, Optional, List, Any

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.spinner import Spinner
from rich.text import Text

from sgr_deep_research.core.agents import (
    BaseAgent,
    BatchGeneratorAgent,
    SGRToolCallingResearchAgent,
    AGENTS,
    DEFAULT_AGENT,
)
from sgr_deep_research.settings import get_config
from sgr_deep_research.flows import research_flow, batch_simple_flow

console = Console()


def setup_logging(debug: bool = False):
    """Настройка логирования."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def display_agents():
    """Показать доступных агентов."""
    console.print("\n[bold cyan]Доступные агенты:[/bold cyan]")
    for key, agent_class in AGENTS.items():
        doc = agent_class.__doc__ or "Нет описания"
        console.print(f"  [green]{key:15}[/green] - {doc.strip().split('.')[0]}")
    console.print()


async def run_agent(
    agent_type: str,
    query: str,
    output_file: Optional[str] = None,
    deep_level: int = 0,
    system_prompt: Optional[str] = None,
    clarifications: bool = False,
    log_file: Optional[str] = None,
    result_dir: Optional[str] = None,
):
    """Запустить агента с заданным запросом."""
    if agent_type not in AGENTS:
        console.print(f"[red]Ошибка:[/red] Неизвестный тип агента '{agent_type}'")
        display_agents()
        return

    agent_class = AGENTS[agent_type]
    
    try:
        console.print(f"\n[bold cyan]Инициализация агента:[/bold cyan] {agent_class.__name__}")
        
        # Настройка глубокого режима - простое масштабирование параметров
        if deep_level > 0:
            # Базовые значения
            base_steps = 6
            base_searches = 4
            
            # Динамическое масштабирование
            max_iterations = base_steps * (deep_level * 3 + 1)  # 6 -> 12/24/36/48
            max_searches = base_searches * (deep_level + 1)     # 4 -> 8/12/16/20
            
            # Создаем агента с увеличенными параметрами
            if hasattr(agent_class, '__init__'):
                import inspect
                sig = inspect.signature(agent_class.__init__)
                kwargs = {'task': query}
                
                if 'max_iterations' in sig.parameters:
                    kwargs['max_iterations'] = max_iterations
                if 'max_searches' in sig.parameters:
                    kwargs['max_searches'] = max_searches
                if 'use_streaming' in sig.parameters:
                    kwargs['use_streaming'] = False  # CLI использует non-streaming для точных токенов
                
                agent = agent_class(**kwargs)
            else:
                agent = agent_class(query, max_iterations=max_iterations)
            
            console.print(f"[bold yellow]🔍 ГЛУБОКИЙ РЕЖИМ УРОВНЯ {deep_level}[/bold yellow]")
            console.print(f"[yellow]Максимум шагов: {max_iterations}[/yellow]")
            console.print(f"[yellow]Максимум поисков: {max_searches}[/yellow]")
            console.print(f"[yellow]Примерное время: {deep_level * 10}-{deep_level * 30} минут[/yellow]")
            
            # Устанавливаем deep_level для использования в параметрах модели
            agent._deep_level = deep_level
            # Переопределяем системный промпт при необходимости
            if system_prompt:
                agent._system_prompt_key_or_file = system_prompt
            
            # Проверяем поддержку GPT-5
            if hasattr(agent, '_get_model_parameters'):
                model_params = agent._get_model_parameters(deep_level)
                if 'max_completion_tokens' in model_params:
                    console.print(f"[dim]GPT-5 режим: {model_params['max_completion_tokens']} токенов, reasoning_effort={model_params.get('reasoning_effort', 'medium')}[/dim]")
                else:
                    console.print(f"[dim]Контекст: {model_params['max_tokens']} токенов[/dim]")
        else:
            # Обычный режим - также отключаем streaming для CLI
            if hasattr(agent_class, '__init__'):
                import inspect
                sig = inspect.signature(agent_class.__init__)
                kwargs = {'task': query}
                
                if 'use_streaming' in sig.parameters:
                    kwargs['use_streaming'] = False  # CLI использует non-streaming для точных токенов
                
                agent = agent_class(**kwargs)
            else:
                agent = agent_class(query)
            
            if system_prompt:
                agent._system_prompt_key_or_file = system_prompt
        
        console.print(f"[bold cyan]Запрос:[/bold cyan] {query}")
        console.print(f"[bold cyan]Модель:[/bold cyan] {agent.model_name}")
        # Показываем только название выбранного системного промпта (пресет или имя файла)
        try:
            from sgr_deep_research.core.prompts import PromptLoader
            # Прогреваем резолвер (без вывода пути)
            _ = PromptLoader.get_system_prompt(
                user_request=query,
                sources=[],
                deep_level=getattr(agent, "_deep_level", 0),
                system_prompt_key_or_file=getattr(agent, "_system_prompt_key_or_file", None),
            )
            # Определяем человекочитаемое название
            cfg = get_config()
            preset_map = getattr(cfg.prompts, 'available_prompts', {}) or {}
            if system_prompt:
                display_name = system_prompt if system_prompt in preset_map else Path(system_prompt).name
            else:
                display_name = 'deep' if getattr(agent, '_deep_level', 0) > 0 else 'default'
            console.print(f"[dim]Системный промпт:[/dim] {display_name}")
        except Exception:
            pass
        console.print()
        
        # Настройка логирования в файл если указан
        file_logger = None
        if log_file:
            import logging
            import os
            # Создаем папку если не существует
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Создаем файловый логгер
            file_logger = logging.getLogger(f"agent_{id(agent)}")
            file_logger.setLevel(logging.INFO)
            
            # Удаляем старые хендлеры
            for handler in file_logger.handlers[:]:
                file_logger.removeHandler(handler)
            
            file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
            file_handler.setFormatter(formatter)
            file_logger.addHandler(file_handler)
            file_logger.propagate = False
            
            # Записываем начальную информацию
            file_logger.info(f"🚀 Агент запущен: {agent_class.__name__}")
            file_logger.info(f"📝 Запрос: {query}")
            file_logger.info(f"🧠 Модель: {agent.model_name}")
            if deep_level > 0:
                file_logger.info(f"🔍 ГЛУБОКИЙ РЕЖИМ УРОВНЯ {deep_level}")
                file_logger.info(f"📊 Максимум шагов: {getattr(agent, 'max_iterations', 'N/A')}")
                file_logger.info(f"🔍 Максимум поисков: {getattr(agent, 'max_searches', 'N/A')}")
        
        # Запуск агента с интерактивной обработкой уточнений
        from sgr_deep_research.core.models import AgentStatesEnum
        
        # Временно изменяем конфигурацию для batch-режима если передан result_dir
        original_reports_dir = None
        if result_dir:
            from sgr_deep_research.settings import get_config
            config = get_config()
            original_reports_dir = config.execution.reports_dir
            config.execution.reports_dir = result_dir
        
        # Запуск агента в фоновом режиме
        agent_task = asyncio.create_task(agent.execute())
        
        # Мониторинг состояния агента
        last_logged_step = 0
        last_logged_state = None
        
        while agent._context.state not in AgentStatesEnum.FINISH_STATES.value:
            # Логируем прогресс агента
            if file_logger:
                current_step = getattr(agent._context, 'step', 0)
                current_state = agent._context.state
                
                # Логируем новые шаги
                if current_step > last_logged_step:
                    file_logger.info(f"📈 Шаг {current_step} выполняется...")
                    last_logged_step = current_step
                
                # Логируем изменения состояния
                if current_state != last_logged_state:
                    if current_state == AgentStatesEnum.RESEARCHING:
                        file_logger.info("⚡ Агент исследует...")
                    elif current_state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                        file_logger.info("❓ Ожидание уточнений...")
                    elif current_state == AgentStatesEnum.COMPLETED:
                        file_logger.info("✅ Работа завершена")
                    elif current_state == AgentStatesEnum.ERROR:
                        file_logger.info("❌ Произошла ошибка")
                    elif current_state == AgentStatesEnum.FAILED:
                        file_logger.info("💥 Задача провалена")
                    else:
                        file_logger.info(f"🔄 Состояние: {current_state}")
                    last_logged_state = current_state
                
                # Логируем выполненные поиски
                current_searches = getattr(agent._context, 'searches_used', 0)
                if hasattr(agent._context, '_last_logged_searches'):
                    last_searches = agent._context._last_logged_searches
                else:
                    last_searches = 0
                    agent._context._last_logged_searches = 0
                
                if current_searches > last_searches:
                    file_logger.info(f"🔍 Выполнен поиск {current_searches}/{getattr(agent, 'max_searches', 'N/A')}")
                    agent._context._last_logged_searches = current_searches
                
                # Логируем активность через streaming generator если доступен
                if hasattr(agent, 'streaming_generator') and hasattr(agent.streaming_generator, '_buffer'):
                    current_buffer_len = len(agent.streaming_generator._buffer)
                    if not hasattr(agent._context, '_last_logged_buffer_len'):
                        agent._context._last_logged_buffer_len = 0
                    
                    # Логируем новые данные в буфере (сокращенно)
                    if current_buffer_len > agent._context._last_logged_buffer_len + 500:  # каждые 500 символов
                        new_content = agent.streaming_generator._buffer[agent._context._last_logged_buffer_len:agent._context._last_logged_buffer_len + 100]
                        if new_content.strip():
                            file_logger.info(f"💭 Агент размышляет: {new_content.strip()[:80]}...")
                        agent._context._last_logged_buffer_len = current_buffer_len
            
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                if not clarifications:
                    # В режиме без уточнений - автоматически продолжаем с пустым ответом
                    console.print("[yellow]⚠️ Режим без уточнений - продолжаем автономно[/yellow]")
                    if file_logger:
                        file_logger.info("⚠️ Режим без уточнений - продолжаем автономно")
                    await agent.provide_clarification("Продолжайте без дополнительных уточнений, используя доступную информацию.")
                else:
                    # Агент ждет уточнений
                    console.print("\n[bold yellow]🤔 Агент запрашивает уточнения:[/bold yellow]")
                    
                    # Получаем последний результат инструмента clarification
                    last_clarification = ""
                    if agent.log:
                        for log_entry in reversed(agent.log):
                            if (log_entry.get("step_type") == "tool_execution" and 
                                log_entry.get("tool_name") == "clarificationtool"):
                                last_clarification = log_entry.get("agent_tool_execution_result", "")
                                break
                    
                    if last_clarification:
                        console.print(Panel(last_clarification, title="Вопросы", border_style="yellow"))
                    
                    # Запрашиваем ответ от пользователя
                    user_answer = Prompt.ask("\n[bold]Ваш ответ[/bold]", default="")
                    
                    if user_answer.strip():
                        # Передаем уточнения агенту
                        await agent.provide_clarification(user_answer)
                        console.print("[green]✅ Уточнения переданы агенту[/green]\n")
                    else:
                        # Пользователь не ответил, завершаем
                        console.print("[yellow]⚠️ Нет ответа, завершаем работу агента[/yellow]")
                        break
            
            await asyncio.sleep(0.1)
        
        # Ждем завершения задачи агента
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        
        # Логируем завершение работы агента
        if file_logger:
            if agent._context.state == AgentStatesEnum.COMPLETED:
                file_logger.info("✅ Агент успешно завершил работу")
                
                # Логируем финальную статистику
                stats = agent.metrics.format_stats()
                for key, value in stats.items():
                    file_logger.info(f"📊 {key}: {value}")
            else:
                file_logger.info(f"❌ Агент завершился с состоянием: {agent._context.state}")

        # Получение результата из контекста агента
        if agent._context.state == AgentStatesEnum.COMPLETED:
            # Попытка найти сгенерированный отчет
            final_answer = ""
            
            # Проверим последние отчеты в папке reports
            reports_dir = Path("reports")
            if reports_dir.exists():
                # Найти самый новый отчет
                report_files = list(reports_dir.glob("*.md"))
                if report_files:
                    latest_report = max(report_files, key=lambda x: x.stat().st_mtime)
                    # Проверить, что отчет создан недавно (в течение последних 5 минут)
                    if (datetime.now().timestamp() - latest_report.stat().st_mtime) < 300:
                        try:
                            with open(latest_report, 'r', encoding='utf-8') as f:
                                final_answer = f.read()
                            console.print(f"[dim]Найден отчет: {latest_report.name}[/dim]")
                        except Exception as e:
                            console.print(f"[yellow]Не удалось прочитать отчет: {e}[/yellow]")
            
            # Если отчет не найден, попробуем получить из других источников
            if not final_answer:
                if hasattr(agent.streaming_generator, '_buffer'):
                    final_answer = agent.streaming_generator._buffer
                elif hasattr(agent, '_final_answer'):
                    final_answer = agent._final_answer
                elif agent._context.searches:
                    final_answer = agent._context.searches[-1].answer or "Исследование завершено."
                else:
                    final_answer = "Исследование завершено, но результат не найден."
            
            # Отображение результата
            console.print("\n" + "="*80 + "\n")
            console.print(Panel(
                Markdown(final_answer),
                title="[bold green]Результат исследования[/bold green]",
                border_style="green"
            ))
            
            # Отображение источников
            sources = list(agent._context.sources.values())
            if sources:
                console.print(f"\n[bold cyan]Источники ({len(sources)}):[/bold cyan]")
                for source in sources:
                    console.print(f"  {source.number}. [link]{source.url}[/link]")
                    if source.title:
                        console.print(f"     {source.title}")
            
            # Отображение статистики выполнения
            console.print(f"\n[bold yellow]📊 Статистика выполнения:[/bold yellow]")
            stats = agent.metrics.format_stats()
            # Укажем какой системный промпт был использован
            try:
                from sgr_deep_research.core.prompts import PromptLoader
                prompt_path = PromptLoader.get_last_resolved_prompt_path()
                if prompt_path:
                    console.print(f"  [cyan]Системный промпт файл:[/cyan] {prompt_path}")
            except Exception:
                pass
            for key, value in stats.items():
                console.print(f"  [cyan]{key}:[/cyan] {value}")
            
            # Сохранение в файл
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"# Результат исследования\n\n")
                    f.write(f"**Запрос:** {query}\n\n")
                    f.write(f"**Агент:** {agent_class.__name__}\n\n")
                    f.write(f"**Модель:** {agent.model_name}\n\n")
                    f.write("## Ответ\n\n")
                    f.write(final_answer)
                    
                    if sources:
                        f.write("\n\n## Источники\n\n")
                        for source in sources:
                            f.write(f"{source.number}. [{source.title or 'Источник'}]({source.url})\n")
                
                console.print(f"\n[green]Результат сохранен в:[/green] {output_path}")
            
            return {"answer": final_answer, "sources": sources}
        else:
            console.print(f"[red]Агент завершился с ошибкой. Состояние:[/red] {agent._context.state}")
            
            # Отображение статистики даже при ошибке
            console.print(f"\n[bold yellow]📊 Статистика выполнения:[/bold yellow]")
            stats = agent.metrics.format_stats()
            try:
                from sgr_deep_research.core.prompts import PromptLoader
                prompt_path = PromptLoader.get_last_resolved_prompt_path()
                if prompt_path:
                    console.print(f"  [cyan]Системный промпт файл:[/cyan] {prompt_path}")
            except Exception:
                pass
            for key, value in stats.items():
                console.print(f"  [cyan]{key}:[/cyan] {value}")
            
            return None
        
    except Exception as e:
        if file_logger:
            file_logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            file_logger.error(f"📜 Traceback: {traceback.format_exc()}")
        
        console.print(f"\n[red]Ошибка при выполнении:[/red] {e}")
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            import traceback
            console.print(f"[red]Traceback:[/red]\n{traceback.format_exc()}")
        return None
    finally:
        # Восстанавливаем исходную конфигурацию
        if original_reports_dir is not None:
            from sgr_deep_research.settings import get_config
            config = get_config()
            config.execution.reports_dir = original_reports_dir


async def run_simple_batch(
    topic: str,
    count: int,
    result_dir: str = "batch_results",
    max_concurrent: int = 3,
) -> Dict[str, Any]:
    """Запускает упрощенный batch через Prefect flow."""
    
    console.print(f"[bold cyan]🚀 Запуск batch исследования[/bold cyan]")
    console.print(f"[cyan]Тема:[/cyan] {topic}")
    console.print(f"[cyan]Количество запросов:[/cyan] {count}")
    console.print(f"[cyan]Параллельно:[/cyan] {max_concurrent}")
    console.print(f"[cyan]Результаты в:[/cyan] {result_dir}")
    
    try:
        console.print("[yellow]⚡ Запускаем Prefect batch flow...[/yellow]")
        
        # Запускаем упрощенный batch flow
        result = await batch_simple_flow(
            topic=topic,
            count=count,
            max_concurrent=max_concurrent,
            result_dir=result_dir,
        )
        
        console.print(f"[green]✅ Batch завершен:[/green]")
        console.print(f"[green]  📊 Выполнено:[/green] {result.get('completed', 0)}")
        console.print(f"[green]  ❌ Ошибок:[/green] {result.get('failed', 0)}")
        console.print(f"[green]  📁 Результаты:[/green] {result.get('result_dir', 'N/A')}")
        
        return result
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка batch исследования:[/red] {e}")
        import traceback
        console.print(f"[red]Traceback:[/red]\n{traceback.format_exc()}")
        return None


async def run_agent_direct(
    query: str,
    deep_level: int = 0,
    output_file: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Запускает SGR tools агента напрямую без Prefect."""
    
    try:
        console.print(f"\n[bold cyan]🔄 Запуск исследования:[/bold cyan] {query}")
        console.print(f"[cyan]Агент:[/cyan] {DEFAULT_AGENT}")
        if deep_level > 0:
            console.print(f"[yellow]🔍 Глубокий режим уровня {deep_level}[/yellow]")
        
        # Базовые параметры для масштабирования
        base_steps = 5
        base_searches = 3
        
        # Динамическое масштабирование для deep режима
        max_iterations = base_steps * (deep_level * 3 + 1) if deep_level > 0 else base_steps
        max_searches = base_searches * (deep_level + 1) if deep_level > 0 else base_searches
        
        console.print(f"[dim]Максимум шагов: {max_iterations}, поисков: {max_searches}[/dim]")
        
        # Создаем SGR tools агента
        agent = SGRToolCallingResearchAgent(
            task=query,
            max_iterations=max_iterations,
            max_searches=max_searches,
            use_streaming=False,  # CLI использует non-streaming
        )
        
        # Запуск агента
        console.print("\n[bold green]▶️ Начинаем выполнение агента...[/bold green]")
        
        # Выполнение с обработкой уточнений
        from sgr_deep_research.core.models import AgentStatesEnum
        
        while True:
            result = await agent.execute()
            
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                # Показываем вопросы пользователю через Rich панель
                clarification_question = agent._context.clarification_question
                
                # Создаем красивую панель для вопроса
                question_panel = Panel(
                    clarification_question,
                    title="[bold yellow]❓ Агент запрашивает уточнение[/bold yellow]",
                    title_align="left",
                    border_style="yellow",
                    padding=(1, 2)
                )
                console.print(question_panel)
                
                # Запрашиваем ответ у пользователя
                user_response = Prompt.ask(
                    "\n[bold cyan]Ваш ответ[/bold cyan]",
                    console=console
                )
                
                if user_response.lower() in ['quit', 'exit', 'q']:
                    console.print("\n[bold yellow]⏹️  Исследование прервано пользователем[/bold yellow]")
                    return None
                
                # Отправляем ответ агенту
                console.print(f"[dim]📤 Отправка ответа агенту...[/dim]")
                await agent.handle_clarification(user_response)
                console.print(f"[dim]✅ Ответ отправлен, продолжаем исследование...[/dim]")
                continue
                
            elif agent._context.state == AgentStatesEnum.COMPLETED:
                # Агент завершил работу успешно
                break
                
            elif agent._context.state == AgentStatesEnum.ERROR:
                console.print(f"[red]❌ Ошибка агента:[/red] {agent._context.error_message}")
                return None
                
            else:
                console.print(f"[yellow]⚠️ Неожиданное состояние агента:[/yellow] {agent._context.state}")
                break
        
        # Получаем результаты
        final_answer = "Исследование завершено."
        
        # Ищем последний отчет
        from pathlib import Path
        from datetime import datetime
        
        reports_dir = Path("reports")
        if reports_dir.exists():
            report_files = list(reports_dir.glob("*.md"))
            if report_files:
                # Берем самый новый файл отчета
                latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
                # Проверяем что файл создан недавно (в течение 5 минут)
                if (datetime.now().timestamp() - latest_report.stat().st_mtime) < 300:
                    try:
                        with open(latest_report, "r", encoding="utf-8") as f:
                            final_answer = f.read()
                        console.print(f"[dim]📄 Найден отчет: {latest_report.name}[/dim]")
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Не удалось прочитать отчет: {e}[/yellow]")
        
        # Сохраняем в output_file если указан
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("# Результат исследования\n\n")
                f.write(f"**Запрос:** {query}\n\n")
                f.write(f"**Агент:** {DEFAULT_AGENT}\n\n")
                if deep_level > 0:
                    f.write(f"**Глубина исследования:** {deep_level}\n\n")
                f.write("## Ответ\n\n")
                f.write(final_answer)
            
            console.print(f"\n[green]📁 Результат сохранен в:[/green] {output_path}")
        
        # Показываем красивую панель с результатами
        sources = list(agent._context.sources.values())
        stats = agent.metrics.format_stats()
        
        # Создаем панель с итогами
        stats_text = f"""[green]📊 Источников найдено:[/green] {len(sources)}
[green]⏱️  Время выполнения:[/green] {stats.get('Время выполнения', 'N/A')}
[green]🔍 Поисковых запросов:[/green] {stats.get('Поисковые запросы', 'N/A')}
[green]💰 Стоимость:[/green] {stats.get('Стоимость (общая)', 'N/A')}
[green]🧠 Шагов выполнено:[/green] {stats.get('Шаги выполнения', 'N/A')}"""

        results_panel = Panel(
            stats_text,
            title="[bold green]✅ Исследование завершено![/bold green]",
            title_align="left",
            border_style="green",
            padding=(1, 2)
        )
        console.print(results_panel)
        
        # Показываем источники если их много
        if len(sources) > 0:
            sources_text = "\n".join([
                f"[cyan]{i+1}.[/cyan] [link={source.url}]{source.title or 'Источник'}[/link]"
                for i, source in enumerate(sources[:5])  # Показываем первые 5
            ])
            
            if len(sources) > 5:
                sources_text += f"\n[dim]... и ещё {len(sources) - 5} источников[/dim]"
            
            sources_panel = Panel(
                sources_text,
                title=f"[bold blue]📚 Источники ({len(sources)})[/bold blue]",
                title_align="left", 
                border_style="blue",
                padding=(1, 2)
            )
            console.print(sources_panel)
        
        return {
            "status": "COMPLETED",
            "answer": final_answer,
            "sources": [{"number": s.number, "url": s.url, "title": s.title} for s in sources],
            "stats": stats,
            "agent_type": DEFAULT_AGENT,
            "deep_level": deep_level,
        }
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка при выполнении агента:[/red] {e}")
        import traceback
        console.print(f"[red]Traceback:[/red]\n{traceback.format_exc()}")
        return None


async def run_agent_with_prefect(
    query: str,
    deep_level: int = 0,
    output_file: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Запускает агента через Prefect flow."""
    
    try:
        console.print(f"\n[bold cyan]🔄 Запуск исследования через Prefect:[/bold cyan] {query}")
        console.print(f"[cyan]Агент:[/cyan] {DEFAULT_AGENT}")
        if deep_level > 0:
            console.print(f"[yellow]🔍 Глубокий режим уровня {deep_level}[/yellow]")
        
        # Запускаем Prefect flow для исследования
        result = await research_flow(
            query=query,
            deep_level=deep_level,
            output_file=output_file,
        )
        
        if result.get("status") == "COMPLETED":
            # Отображение результата
            console.print("\n" + "="*80 + "\n")
            console.print(Panel(
                Markdown(result.get("answer", "")),
                title="[bold green]Результат исследования (Prefect)[/bold green]",
                border_style="green"
            ))
            
            # Отображение источников
            sources = result.get("sources", [])
            if sources:
                console.print(f"\n[bold cyan]Источники ({len(sources)}):[/bold cyan]")
                for source in sources:
                    console.print(f"  {source['number']}. [link]{source['url']}[/link]")
                    if source['title']:
                        console.print(f"     {source['title']}")
            
            # Отображение статистики выполнения
            console.print(f"\n[bold yellow]📊 Статистика выполнения:[/bold yellow]")
            stats = result.get("stats", {})
            console.print(f"  [cyan]Агент:[/cyan] {result.get('agent_type', 'Unknown')}")
            console.print(f"  [cyan]Модель:[/cyan] {result.get('model', 'Unknown')}")
            if deep_level > 0:
                console.print(f"  [cyan]Глубина:[/cyan] {deep_level}")
            for key, value in stats.items():
                console.print(f"  [cyan]{key}:[/cyan] {value}")
            
            if output_file:
                console.print(f"\n[green]Результат сохранен в:[/green] {output_file}")
            
            return result
        else:
            console.print(f"[red]Агент завершился с ошибкой:[/red] {result.get('error', 'Unknown error')}")
            return None
    
    except Exception as e:
        console.print(f"\n[red]Ошибка при выполнении через Prefect:[/red] {e}")
        import traceback
        console.print(f"[red]Traceback:[/red]\n{traceback.format_exc()}")
        return None


async def execute_single_query(
    line_num: int,
    query: str,
    batch_dir: Path,
    agent_type: str,
    suggested_depth: int = 0,
    semaphore: asyncio.Semaphore = None,
    clarifications: bool = False,
) -> tuple[int, bool]:
    """Выполняет один запрос из batch плана."""
    if semaphore:
        async with semaphore:
            return await _execute_query_impl(line_num, query, batch_dir, agent_type, suggested_depth, not clarifications)
    else:
        return await _execute_query_impl(line_num, query, batch_dir, agent_type, suggested_depth, not clarifications)


async def _execute_query_impl(
    line_num: int,
    query: str, 
    batch_dir: Path,
    agent_type: str,
    suggested_depth: int = 0,
    clarifications: bool = False,
) -> tuple[int, bool]:
    """Внутренняя реализация выполнения запроса."""
    try:
        # Создаем папку для результата
        result_dir = batch_dir / f"{line_num:02d}_result"
        result_dir.mkdir(exist_ok=True)
        
        output_file = result_dir / "report.md"
        log_file = result_dir / "agent.log"
        
        console.print(f"[cyan]🔄 Строка {line_num}:[/cyan] Выполняем запрос...")
        
        # Выполняем запрос с логированием
        result = await run_agent(
            agent_type=agent_type,
            query=query,
            output_file=str(output_file),
            deep_level=suggested_depth,
            clarifications=clarifications,
            log_file=str(log_file),
            result_dir=str(result_dir),  # Передаем путь для сохранения отчетов
        )
        
        if result:
            # Сохраняем метаданные выполнения
            meta_file = result_dir / "execution.json"
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump({
                    "line_number": line_num,
                    "query": query,
                    "agent_type": agent_type,
                    "suggested_depth": suggested_depth,
                    "completed_at": datetime.now().isoformat(),
                    "status": "COMPLETED",
                    "output_file": str(output_file),
                }, f, ensure_ascii=False, indent=2)
            
            console.print(f"[green]✅ Строка {line_num} завершена[/green]")
            return line_num, True
        else:
            console.print(f"[red]❌ Строка {line_num} завершилась с ошибкой[/red]")
            return line_num, False
            
    except Exception as e:
        console.print(f"[red]❌ Ошибка в строке {line_num}:[/red] {e}")
        return line_num, False


async def run_simple_batch(
    topic: str,
    count: int = 5,
    agent_type: str = DEFAULT_AGENT,
    max_concurrent: int = 3,
    result_dir: str = "batch_results",
) -> None:
    """Выполняет упрощенное batch-исследование используя новый batch_simple_flow."""
    
    console.print(f"[bold cyan]🚀 Упрощенное batch исследование[/bold cyan]")
    console.print(f"[cyan]Тема:[/cyan] {topic}")
    console.print(f"[cyan]Количество запросов:[/cyan] {count}")
    console.print(f"[cyan]Агент:[/cyan] {agent_type}")
    console.print(f"[cyan]Максимум параллельных задач:[/cyan] {max_concurrent}")
    
    try:
        console.print("[yellow]⚡ Запускаем упрощенный Prefect flow...[/yellow]")
        
        # Запускаем упрощенный Prefect flow
        result = await batch_simple_flow(
            topic=topic,
            count=count,
            agent_type=agent_type,
            max_concurrent=max_concurrent,
            result_dir=result_dir,
        )
        
        if result.get("status") == "COMPLETED":
            console.print(f"\n[bold green]🎉 Batch исследование завершено![/bold green]")
            console.print(f"[green]✅ Успешно:[/green] {result['completed']}/{result['total_queries']}")
            if result['failed'] > 0:
                console.print(f"[red]❌ Ошибок:[/red] {result['failed']}")
            if result['exceptions'] > 0:
                console.print(f"[red]💥 Исключений:[/red] {result['exceptions']}")
            console.print(f"[green]📁 Результаты в:[/green] {result['result_dir']}")
            
            # Показываем сгенерированные запросы
            queries = result.get('queries', [])
            if queries:
                console.print(f"\n[bold blue]📝 Сгенерированные запросы ({len(queries)}):[/bold blue]")
                for i, query in enumerate(queries[:10], 1):  # Показываем первые 10
                    console.print(f"  [cyan]{i:2d}.[/cyan] {query.get('query', 'N/A')}")
                if len(queries) > 10:
                    console.print(f"  [dim]... и ещё {len(queries) - 10} запросов[/dim]")
        else:
            console.print(f"[red]❌ Batch завершился с ошибкой: {result.get('error', 'Unknown error')}[/red]")
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка выполнения batch:[/red] {e}")
        import traceback
        console.print(f"[red]Traceback:[/red]\n{traceback.format_exc()}")


async def run_batch(
    batch_name: str,
    agent_type: str = DEFAULT_AGENT,
    force_restart: bool = False,
) -> None:
    """Выполняет batch-исследование."""
    batch_dir = Path("batches") / batch_name
    
    if not batch_dir.exists():
        console.print(f"[red]❌ Batch '{batch_name}' не найден в:[/red] {batch_dir}")
        return
    
    plan_file = batch_dir / "plan.json"
    status_file = batch_dir / "status.txt"
    
    if not plan_file.exists():
        console.print(f"[red]❌ Файл плана не найден:[/red] {plan_file}")
        return
    
    # Загружаем план
    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            plan_data = json.load(f)
        
        from sgr_deep_research.core.agents.batch_generator_agent import BatchPlan
        batch_plan = BatchPlan(**plan_data)
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка загрузки плана:[/red] {e}")
        return
    
    console.print(f"[bold cyan]🚀 Запуск batch исследования '{batch_name}'[/bold cyan]")
    console.print(f"[cyan]Тема:[/cyan] {batch_plan.topic}")
    console.print(f"[cyan]Запросов:[/cyan] {len(batch_plan.queries)}")
    console.print(f"[cyan]Агент:[/cyan] {agent_type}")
    
    # Читаем текущий статус
    completed_queries = set()
    if status_file.exists() and not force_restart:
        with open(status_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("[COMPLETED]"):
                    # Извлекаем ID запроса
                    match = re.search(r"\[COMPLETED\]\s+(\d+)\.", line)
                    if match:
                        completed_queries.add(int(match.group(1)))
    
    # Определяем запросы для выполнения
    queries_to_run = [q for q in batch_plan.queries if q.id not in completed_queries]
    
    if not queries_to_run:
        console.print("[green]✅ Все запросы уже выполнены![/green]")
        return
    
    console.print(f"[yellow]📋 К выполнению: {len(queries_to_run)} из {len(batch_plan.queries)} запросов[/yellow]")
    
    if not force_restart and len(completed_queries) > 0:
        console.print(f"[dim]Пропускаем {len(completed_queries)} уже выполненных запросов[/dim]")
    
    # Выполняем запросы
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        
        task = progress.add_task(f"Batch {batch_name}", total=len(queries_to_run))
        
        for query in queries_to_run:
            # Обновляем статус на RUNNING
            update_query_status(status_file, query.id, "RUNNING")
            
            progress.update(task, description=f"[cyan]Запрос {query.id:02d}:[/cyan] {query.aspect}")
            
            # Создаем папку для результата
            query_dir = batch_dir / f"query_{query.id:02d}_{query.aspect.replace(' ', '_')}"
            query_dir.mkdir(exist_ok=True)
            
            output_file = query_dir / "result.md"
            
            try:
                # Выполняем запрос
                result = await run_agent(
                    agent_type=agent_type,
                    query=query.query,
                    output_file=str(output_file),
                    deep_level=query.suggested_depth,
                )
                
                if result:
                    # Сохраняем метаданные
                    meta_file = query_dir / "metadata.json"
                    with open(meta_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "id": query.id,
                            "query": query.query,
                            "query_en": query.query_en,
                            "aspect": query.aspect,
                            "scope": query.scope,
                            "suggested_depth": query.suggested_depth,
                            "agent_type": agent_type,
                            "completed_at": datetime.now().isoformat(),
                            "status": "COMPLETED",
                        }, f, ensure_ascii=False, indent=2)
                    
                    update_query_status(status_file, query.id, "COMPLETED")
                    console.print(f"[green]✅ Запрос {query.id} завершен[/green]")
                else:
                    update_query_status(status_file, query.id, "ERROR")
                    console.print(f"[red]❌ Запрос {query.id} завершился с ошибкой[/red]")
                
            except Exception as e:
                console.print(f"[red]❌ Ошибка в запросе {query.id}:[/red] {e}")
                update_query_status(status_file, query.id, "ERROR")
            
            progress.advance(task)
    
    console.print(f"\n[bold green]🎉 Batch исследование '{batch_name}' завершено![/bold green]")
    console.print(f"[green]📁 Результаты в:[/green] {batch_dir}")


def update_query_status(status_file: Path, query_id: int, new_status: str) -> None:
    """Обновляет статус запроса в файле."""
    if not status_file.exists():
        return
    
    # Читаем файл
    with open(status_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Обновляем строку с нужным ID
    for i, line in enumerate(lines):
        if re.search(rf"\[.*\]\s+{query_id:02d}\.", line):
            # Заменяем статус
            lines[i] = re.sub(r"\[.*?\]", f"[{new_status}]", line)
            break
    
    # Записываем обратно
    with open(status_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def list_batches() -> None:
    """Показывает список существующих batch-исследований."""
    batches_dir = Path("batches")
    
    if not batches_dir.exists():
        console.print("[yellow]📁 Папка batches не найдена[/yellow]")
        return
    
    batch_dirs = [d for d in batches_dir.iterdir() if d.is_dir()]
    
    if not batch_dirs:
        console.print("[yellow]📁 Batch-исследования не найдены[/yellow]")
        return
    
    console.print(f"[bold cyan]📋 Найдено {len(batch_dirs)} batch-исследований:[/bold cyan]\n")
    
    for batch_dir in sorted(batch_dirs):
        batch_name = batch_dir.name
        plan_file = batch_dir / "plan.txt"
        meta_file = batch_dir / "metadata.json"
        
        # Читаем тему и общую информацию
        topic = "Неизвестная тема"
        total_queries = 0
        
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    topic = meta.get("topic", topic)
                    total_queries = meta.get("total_queries", 0)
            except:
                pass
        elif plan_file.exists():
            # Fallback: считаем строки в плане
            try:
                with open(plan_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith("#"):
                            total_queries += 1
                        elif line.strip().startswith("# Topic:"):
                            topic = line.strip()[8:].strip()
            except:
                pass
        
        # Анализируем статус выполнения
        completed_queries = 0
        error_queries = 0
        
        for i in range(1, total_queries + 1):
            result_dir = batch_dir / f"{i:02d}_result"
            exec_file = result_dir / "execution.json"
            
            if exec_file.exists():
                try:
                    with open(exec_file, "r", encoding="utf-8") as f:
                        exec_data = json.load(f)
                        if exec_data.get("status") == "COMPLETED":
                            completed_queries += 1
                        else:
                            error_queries += 1
                except:
                    error_queries += 1
        
        # Определяем общий статус
        if completed_queries == total_queries and total_queries > 0:
            status_color = "green"
            status_text = "✅ ЗАВЕРШЕН"
        elif completed_queries > 0:
            status_color = "yellow"
            status_text = "🔄 ЧАСТИЧНО"
        elif error_queries > 0:
            status_color = "red"
            status_text = "❌ ОШИБКИ"
        else:
            status_color = "blue"
            status_text = "⏳ ОЖИДАЕТ"
        
        console.print(f"[bold]{batch_name}[/bold]")
        console.print(f"  [dim]Тема:[/dim] {topic}")
        console.print(f"  [{status_color}]Статус:[/{status_color}] {status_text}")
        console.print(f"  [dim]Прогресс:[/dim] {completed_queries}/{total_queries}")
        if error_queries > 0:
            console.print(f"  [red]Ошибок:[/red] {error_queries}")
        console.print()


def show_batch_status(batch_name: str) -> None:
    """Показывает детальный статус batch исследования."""
    batch_dir = Path("batches") / batch_name
    
    if not batch_dir.exists():
        console.print(f"[red]❌ Batch '{batch_name}' не найден в:[/red] {batch_dir}")
        return
    
    plan_file = batch_dir / "plan.txt"
    meta_file = batch_dir / "metadata.json"
    
    # Загружаем план
    queries = []
    topic = "Неизвестная тема"
    
    if plan_file.exists():
        with open(plan_file, "r", encoding="utf-8") as f:
            actual_line_num = 0
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    actual_line_num += 1
                    queries.append((actual_line_num, line))
                elif line.startswith("# Topic:"):
                    topic = line[8:].strip()
    
    # Загружаем метаданные
    queries_meta = {}
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                topic = meta.get("topic", topic)
                for qmeta in meta.get("queries_meta", []):
                    queries_meta[qmeta["line"]] = qmeta
        except Exception as e:
            console.print(f"[yellow]⚠️ Не удалось загрузить метаданные: {e}[/yellow]")
    
    if not queries:
        console.print("[red]❌ Не найдены запросы в плане[/red]")
        return
    
    console.print(f"[bold cyan]📋 Batch исследование: {batch_name}[/bold cyan]")
    console.print(f"[cyan]Тема:[/cyan] {topic}")
    console.print(f"[cyan]Запросов:[/cyan] {len(queries)}")
    console.print(f"\n[bold yellow]📊 Статус выполнения:[/bold yellow]")
    
    # Показываем статус каждого запроса
    for line_num, query in queries:
        result_dir = batch_dir / f"{line_num:02d}_result"
        exec_file = result_dir / "execution.json"
        
        # Определяем статус
        if exec_file.exists():
            try:
                with open(exec_file, "r", encoding="utf-8") as f:
                    exec_data = json.load(f)
                    status = exec_data.get("status", "UNKNOWN")
                    completed_at = exec_data.get("completed_at", "")
                    
                if status == "COMPLETED":
                    status_color = "green"
                    status_icon = "✅"
                    status_text = f"COMPLETED ({completed_at[:16]})"
                else:
                    status_color = "red"
                    status_icon = "❌"
                    status_text = "ERROR"
            except:
                status_color = "red"
                status_icon = "❌"
                status_text = "ERROR (корр. файл)"
        else:
            status_color = "dim"
            status_icon = "⏳"
            status_text = "PENDING"
        
        # Показываем запрос с метаданными
        console.print(f"  [{status_color}]{status_icon} {line_num:02d}.[/{status_color}] {status_text}")
        
        # Показываем сокращенный запрос
        short_query = query[:80] + "..." if len(query) > 80 else query
        console.print(f"      [dim]{short_query}[/dim]")
        
        # Показываем метаданные если есть
        if line_num in queries_meta:
            qmeta = queries_meta[line_num]
            console.print(f"      [dim]Аспект: {qmeta.get('aspect', 'N/A')}, "
                         f"Глубина: {qmeta.get('suggested_depth', 0)}[/dim]")
        
        # Показываем путь к результату если есть
        if exec_file.exists():
            report_file = result_dir / "report.md"
            if report_file.exists():
                console.print(f"      [dim]Отчет: {report_file}[/dim]")
        
        console.print()


async def interactive_mode():
    """Интерактивный режим работы."""
    console.print("[bold cyan]🔍 SGR Deep Research - Интерактивный режим[/bold cyan]")
    console.print("Введите 'help' для справки, 'quit' для выхода\n")
    
    current_agent = DEFAULT_AGENT  # По умолчанию
    
    while True:
        try:
            command = Prompt.ask(f"[{current_agent}]", default="").strip()
            
            if not command or command.lower() in ["quit", "exit", "q"]:
                console.print("[yellow]До свидания![/yellow]")
                break
            
            if command.lower() == "help":
                console.print("\n[bold cyan]Команды:[/bold cyan]")
                console.print("  help                    - Показать эту справку")
                console.print("  agents                  - Показать доступных агентов")
                console.print("  agent <type>            - Переключиться на агента")
                console.print("  deep <запрос>           - Глубокое исследование (20 шагов)")
                console.print("  deep2 <запрос>          - Очень глубокое (40 шагов, ~20-60 мин)")
                console.print("  deep3 <запрос>          - Экстремально глубокое (60 шагов, ~30-90 мин)")
                console.print("  [bold yellow]Batch режим:[/bold yellow]")
                console.print("  batches                 - Показать список batch-исследований")
                console.print("  batch create <название> <количество> <тема> - Создать batch план")
                console.print("  batch run <название>    - Запустить batch исследование")
                console.print("  batch status <название> - Показать статус batch")
                console.print("  quit/exit/q             - Выход")
                console.print("  <запрос>                - Выполнить исследование")
                console.print()
                continue
            
            if command.lower() == "agents":
                display_agents()
                continue
            
            if command.lower().startswith("agent "):
                new_agent = command[6:].strip()
                if new_agent in AGENTS:
                    current_agent = new_agent
                    console.print(f"[green]Переключились на агента:[/green] {new_agent}")
                else:
                    console.print(f"[red]Неизвестный агент:[/red] {new_agent}")
                    display_agents()
                continue
            
            # Batch команды
            if command.lower() == "batches":
                list_batches()
                continue
            
            if command.lower().startswith("batch "):
                batch_args = command[6:].split()
                
                if len(batch_args) == 0:
                    console.print("[red]Укажите подкоманду:[/red] create, run, status")
                    continue
                
                batch_cmd = batch_args[0].lower()
                
                if batch_cmd == "create":
                    if len(batch_args) < 4:
                        console.print("[red]Использование:[/red] batch create <название> <количество> <тема>")
                        console.print("[yellow]Пример:[/yellow] batch create bashkir_history 10 история башкир")
                        continue
                    
                    batch_name = batch_args[1]
                    try:
                        count = int(batch_args[2])
                    except ValueError:
                        console.print("[red]Количество должно быть числом[/red]")
                        continue
                    
                    topic = " ".join(batch_args[3:])
                    
                    await create_batch_plan(topic, batch_name, count)
                    continue
                
                elif batch_cmd == "run":
                    if len(batch_args) < 2:
                        console.print("[red]Использование:[/red] batch run <название> [parallel|sequential]")
                        continue
                    
                    batch_name = batch_args[1]
                    run_mode = batch_args[2] if len(batch_args) > 2 else "parallel"
                    
                    if run_mode == "parallel":
                        await run_batch_parallel(batch_name, current_agent, max_concurrent=3)
                    else:
                        await run_batch(batch_name, current_agent)
                    continue
                
                elif batch_cmd == "status":
                    if len(batch_args) < 2:
                        console.print("[red]Использование:[/red] batch status <название>")
                        continue
                    
                    batch_name = batch_args[1]
                    show_batch_status(batch_name)
                    continue
                
                else:
                    console.print(f"[red]Неизвестная batch команда:[/red] {batch_cmd}")
                    console.print("[yellow]Доступные:[/yellow] create, run, status")
                    continue
            
            # Выполнить исследование
            deep_level = 0
            if command.startswith("deep"):
                if command.startswith("deep "):
                    deep_level = 1
                    command = command[5:]  # Убрать "deep " из начала
                else:
                    # Проверяем паттерн deep1, deep2, deep3 и т.д.
                    import re
                    match = re.match(r"deep(\d+)\s+(.+)", command)
                    if match:
                        deep_level = int(match.group(1))
                        command = match.group(2)
                    else:
                        # Проверяем просто deep1, deep2 без пробела
                        match = re.match(r"deep(\d+)$", command.split()[0])
                        if match and len(command.split()) > 1:
                            deep_level = int(match.group(1))
                            command = " ".join(command.split()[1:])
                
                if deep_level > 0:
                    console.print(f"[yellow]🔍 Глубокий режим уровня {deep_level} (время: ~{deep_level * 10}-{deep_level * 30} мин)[/yellow]")
            
            await run_agent_direct(command, deep_level=deep_level)
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Прервано пользователем[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка:[/red] {e}")


@click.group(invoke_without_command=True)
@click.option('--query', '-q', help='Запрос для исследования')
@click.option('--agent', '-a', 
              type=click.Choice(list(AGENTS.keys())), 
              default='sgr-tools',
              help='Тип агента (по умолчанию: sgr-tools)')
@click.option('--output', '-o', help='Файл для сохранения результата (Markdown)')
@click.option('--deep', type=int, default=0, 
              help='Уровень глубокого исследования (1-5+: 1=20 шагов, 2=40 шагов, 3=60 шагов...)')
@click.option('--system-prompt', 'system_prompt', type=str, default=None,
              help='Имя пресета из config.prompts.available_prompts или имя файла из папки prompts')
@click.option('--debug', is_flag=True, help='Включить отладочный вывод')
@click.option('--interactive', '-i', is_flag=True, help='Запустить в интерактивном режиме')
@click.pass_context
def cli(ctx, query, agent, output, deep, system_prompt, debug, interactive):
    """SGR Deep Research CLI
    
    Примеры использования:
    
      # Интерактивный режим
      uv run python -m sgr_deep_research.cli
    
      # Быстрый запрос
      uv run python -m sgr_deep_research.cli --query "Что такое квантовые компьютеры?"
    
      # Использование конкретного агента
      uv run python -m sgr_deep_research.cli --agent sgr-tools --query "Последние новости AI"
    
      # Сохранение результата в файл
      uv run python -m sgr_deep_research.cli --query "Python async/await" --output report.md
    """
    setup_logging(debug)
    
    try:
        # Проверка конфигурации
        config = get_config()
        console.print(f"[dim]Конфигурация загружена: {config.tavily.api_base_url}[/dim]")
    except Exception as e:
        console.print(f"[red]Ошибка конфигурации:[/red] {e}")
        sys.exit(1)
    
    # Если команда не вызвана, запускаем основную логику
    if ctx.invoked_subcommand is None:
        if interactive or not query:
            asyncio.run(interactive_mode())
        else:
            # Выполнить одиночный запрос напрямую
            asyncio.run(run_agent_direct(query, deep, output))


@cli.command()
def agents():
    """Показать доступных агентов."""
    display_agents()


@cli.command()
@click.argument('query')
@click.option('--level', '-l', type=int, default=1, help='Уровень глубины (1-5+)')
@click.option('--agent', '-a', 
              type=click.Choice(list(AGENTS.keys())), 
              default='sgr-tools',
              help='Тип агента')
@click.option('--output', '-o', help='Файл для сохранения результата')
def deep(query, level, agent, output):
    """Глубокое исследование (без Prefect).
    
    Уровни глубины:
    1 - ~20 шагов, 10-30 мин
    2 - ~40 шагов, 20-60 мин  
    3 - ~60 шагов, 30-90 мин
    4+ - ~80+ шагов, 40+ мин
    """
    asyncio.run(run_agent_direct(query, level, output))


@cli.command()
@click.argument('topic')
@click.option('--count', '-c', type=int, default=5, help='Количество запросов для генерации')
@click.option('--agent', '-a', 
              type=click.Choice(list(AGENTS.keys())), 
              default='sgr-tools',
              help='Тип агента')
@click.option('--concurrent', '-j', type=int, default=3, help='Максимум параллельных задач')
@click.option('--output-dir', '-o', default='batch_results', help='Папка для результатов')
def batch(topic, count, agent, concurrent, output_dir):
    """Батч исследование - множественные запросы по теме (с Prefect).
    
    Примеры:
        uv run python -m sgr_deep_research.cli batch "современные AI технологии"
        uv run python -m sgr_deep_research.cli batch "история башкир" --count 10 --concurrent 2
    """
    asyncio.run(run_simple_batch(topic, count, agent, concurrent, output_dir))


def main():
    """Точка входа CLI."""
    cli()


if __name__ == "__main__":
    main()
