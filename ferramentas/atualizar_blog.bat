@echo off
rem Atualiza o blog do site com o WG Jornal do dia e publica no GitHub Pages.
rem Uso: dar dois cliques (precisa de Python e Git instalados, e acesso à pasta N:\ do jornal).
setlocal
cd /d "%~dp0.."
python -X utf8 ferramentas\atualizar_blog.py || goto :erro
git add -A
git commit -m "Blog: noticias do WG Jornal de %date%" || echo Nada novo para publicar.
git push origin main || goto :erro
echo.
echo Blog publicado. O link leva alguns minutos para atualizar.
pause
exit /b 0
:erro
echo.
echo Deu erro em alguma etapa (veja as mensagens acima).
pause
exit /b 1
