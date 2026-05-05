@echo off
cd /d "C:\Users\Bruno Campos\Desktop\Nova pasta\licitacoes-ai"
python -c "import sys; sys.path.insert(0, '.'); from agente1_monitor.main import executar_monitor; executar_monitor(usar_llm=False, dias_retroativos=1)" >> data\skills\monitor.log 2>&1
