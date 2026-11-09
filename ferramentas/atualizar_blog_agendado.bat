@echo off
rem Versao silenciosa para o Agendador de Tarefas do Windows: atualiza o blog com o
rem WG Jornal do dia e publica no GitHub so quando houver noticia nova.
rem O que aconteceu fica em ferramentas\atualizar_blog.log.
setlocal
cd /d "%~dp0.."
set "LOG=%~dp0atualizar_blog.log"
set GIT_TERMINAL_PROMPT=0
echo ==== %date% %time% >> "%LOG%"
python -X utf8 ferramentas\atualizar_blog.py >> "%LOG%" 2>&1 || (echo ERRO: o gerador do blog falhou >> "%LOG%" & exit /b 1)
git add -A >> "%LOG%" 2>&1
git diff --cached --quiet && (echo Nada novo para publicar. >> "%LOG%" & exit /b 0)
git commit -m "Blog: noticias do WG Jornal" >> "%LOG%" 2>&1 || (echo ERRO: commit falhou >> "%LOG%" & exit /b 1)
git push origin main >> "%LOG%" 2>&1 || (echo ERRO: push falhou >> "%LOG%" & exit /b 1)
echo Publicado. >> "%LOG%"
exit /b 0
