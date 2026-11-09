@echo off
rem Publica o site novo da WG na Locaweb (ao lado do WordPress, sem apagar nada).
rem Pede o servidor, o usuario e a senha do FTP na tela; a senha nao fica gravada.
rem Para voltar ao WordPress: ferramentas\publicar_locaweb.bat --desfazer
setlocal
cd /d "%~dp0.."
python -X utf8 ferramentas\publicar_locaweb.py %*
echo.
pause
