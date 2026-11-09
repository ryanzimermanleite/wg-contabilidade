"""Publica o site novo da WG na hospedagem da Locaweb, AO LADO do WordPress atual.

Nada do WordPress é apagado. O site novo entra na raiz (index.html, privacidade.html e a
pasta blog/) e um bloco no topo do .htaccess faz a página inicial abrir o site novo e leva
os endereços antigos para as seções equivalentes. Continuam funcionando: /wp-content (o logo
dos e-mails do WG Jornal), /wp-admin e o subdomínio do BI.

Uso, num terminal aberto na pasta do site:
    python ferramentas/publicar_locaweb.py              publica (pede servidor, usuário e senha do FTP)
    python ferramentas/publicar_locaweb.py --simular    mostra o que seria feito, sem conectar
    python ferramentas/publicar_locaweb.py --atualizar  envia só o que mudou desde a última publicação
    python ferramentas/publicar_locaweb.py --desfazer   tira o site novo e volta o WordPress como estava

A senha é digitada na hora e não fica gravada. Para rodar sem perguntas (ex.: tarefa agendada),
defina as variáveis de ambiente WG_FTP_HOST, WG_FTP_USUARIO e WG_FTP_SENHA e use --sem-perguntar.

O FTP da Locaweb tem manias (conferidas em 2026): só aceita TLS com cifras antigas e certificado autoassinado,
e no canal de dados a ordem é comando, aperto de mão TLS e só então a resposta 150 (na ordem padrão do ftplib
os dois lados ficam esperando). A conexão abaixo (FTPSLocaweb) já faz assim.

O que já subiu fica anotado em backups_locaweb/publicado.json (nome do arquivo e impressão digital); com
--atualizar só vai o que mudou, e sem nada novo nem conecta.
"""
from __future__ import annotations

import argparse
import ftplib
import getpass
import hashlib
import io
import json
import os
import socket
import ssl
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOMINIO = "wgcontabilidade.com.br"
HOST_PADRAO = "ftp.wgcontabilidade.com.br"
MARCA_INI = "# BEGIN Site novo WG"
MARCA_FIM = "# END Site novo WG"
TEXTO_DO_SITE_NOVO = "Um único escritório."     # aparece só na página inicial nova
LOGO_DOS_EMAILS = f"https://{DOMINIO}/wp-content/uploads/2018/09/cropped-logo-wg-contabilidade.png"
PASTA_BACKUPS = RAIZ / "backups_locaweb"
MANIFESTO = PASTA_BACKUPS / "publicado.json"
NA_RAIZ_TAMBEM = ("sitemap.xml", "robots.txt")      # o sitemap e o robots do site novo (os antigos vão para o backup)
PERGUNTAR = True

# Redirecionamentos temporários (302) enquanto o site novo é avaliado; trocar por 301 depois
# que estiver aprovado, para o Google transferir a relevância das páginas antigas.
BLOCO_HTACCESS = r"""# BEGIN Site novo WG
# Gerado por ferramentas/publicar_locaweb.py. Para voltar ao WordPress, rode o script com
# --desfazer (ou apague este bloco e os arquivos index.html, privacidade.html e a pasta blog).
DirectoryIndex index.html index.php
<IfModule mod_rewrite.c>
RewriteEngine On
# um endereço só: https://wgcontabilidade.com.br (sem www), mantendo o caminho
RewriteCond %{HTTP_HOST} ^www\.wgcontabilidade\.com\.br$ [NC]
RewriteRule ^(.*)$ https://wgcontabilidade.com.br/$1 [R=301,L]
RewriteCond %{HTTP_HOST} ^wgcontabilidade\.com\.br$ [NC]
RewriteCond %{SERVER_PORT} 80
RewriteRule ^(.*)$ https://wgcontabilidade.com.br/$1 [R=301,L]
RewriteCond %{HTTP_HOST} ^(www\.)?wgcontabilidade\.com\.br$ [NC]
RewriteRule ^(contabilidade|escrita-fiscal|departamento-pessoal|recursos-humanos|servicos|abertura-de-empresas)/?$ /#servicos [R=302,NE,L]
RewriteCond %{HTTP_HOST} ^(www\.)?wgcontabilidade\.com\.br$ [NC]
RewriteRule ^a-empresa/?$ /#diferenciais [R=302,NE,L]
RewriteCond %{HTTP_HOST} ^(www\.)?wgcontabilidade\.com\.br$ [NC]
RewriteRule ^fale-conosco/?$ /#contato [R=302,NE,L]
RewriteCond %{HTTP_HOST} ^(www\.)?wgcontabilidade\.com\.br$ [NC]
RewriteRule ^politica-de-privacidade/?$ /privacidade.html [R=302,L]
# demais páginas e posts antigos do WordPress vão para a página inicial; arquivos e pastas
# que existem (como /wp-content e /blog) e as rotas do WordPress listadas abaixo seguem normais
RewriteCond %{HTTP_HOST} ^(www\.)?wgcontabilidade\.com\.br$ [NC]
RewriteCond %{REQUEST_URI} !^/(wp-admin|wp-content|wp-includes|wp-json|wp-login\.php|wp-cron\.php|xmlrpc\.php|\.well-known)
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^.+$ / [R=302,L]
</IfModule>
# END Site novo WG
"""


# ------------------------------------------------------------------ arquivos e .htaccess
def arquivos_do_site() -> list[tuple[str, Path]]:
    """(caminho no servidor, arquivo local) — blog primeiro, página inicial por último."""
    lista = [(f"blog/{p.name}", p) for p in sorted((RAIZ / "blog").glob("*.html"))]
    lista.append(("privacidade.html", RAIZ / "privacidade.html"))
    lista += [(n, RAIZ / n) for n in NA_RAIZ_TAMBEM if (RAIZ / n).exists()]
    lista.append(("index.html", RAIZ / "index.html"))
    faltando = [str(p) for _, p in lista if not p.exists()]
    if faltando:
        sys.exit(f"Arquivos do site não encontrados: {faltando}")
    return lista


def tirar_bloco(htaccess: str) -> str:
    """Remove o bloco do site novo (se houver) e devolve o resto como estava."""
    if MARCA_INI not in htaccess:
        return htaccess
    antes, _, resto = htaccess.partition(MARCA_INI)
    _, _, depois = resto.partition(MARCA_FIM)
    return (antes + depois.lstrip("\r\n")).lstrip("\r\n")


def com_bloco(htaccess: str) -> str:
    """Põe o bloco do site novo no topo; o que já existia (regras do WordPress) fica logo abaixo."""
    resto = tirar_bloco(htaccess)
    return BLOCO_HTACCESS + ("\n" + resto if resto.strip() else "")


# ------------------------------------------------------------------ FTP
def credenciais() -> tuple[str, str, str]:
    host = os.environ.get("WG_FTP_HOST") or input(f"Servidor FTP [{HOST_PADRAO}]: ").strip() or HOST_PADRAO
    usuario = os.environ.get("WG_FTP_USUARIO") or input("Usuário do FTP: ").strip()
    senha = os.environ.get("WG_FTP_SENHA") or getpass.getpass("Senha do FTP (não aparece ao digitar): ")
    if not usuario or not senha:
        sys.exit("Usuário e senha são obrigatórios.")
    return host, usuario, senha


class FTPSLocaweb(ftplib.FTP_TLS):
    """FTPS do jeito que o servidor da Locaweb aceita: no canal de dados manda o comando, faz o aperto de mão TLS
    (reaproveitando a sessão do canal de controle) e só depois lê a resposta 150."""

    def ntransfercmd(self, cmd, rest=None):
        host, porta = self.makepasv()
        conn = socket.create_connection((host, porta), self.timeout)
        try:
            if rest is not None:
                self.sendcmd(f"REST {rest}")
            self.putcmd(cmd)
            if self._prot_p:
                conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
            resp = self.getresp()
            if resp[0] == "2":
                resp = self.getresp()
            if resp[0] != "1":
                raise ftplib.error_reply(resp)
        except BaseException:
            conn.close()
            raise
        return conn, (ftplib.parse150(resp) if resp[:3] == "150" else None)


def contexto_tls() -> ssl.SSLContext:
    """TLS 1.2+ com as cifras antigas que o servidor exige; o certificado dele é autoassinado (o canal vai
    cifrado, sem validar a cadeia, o que ainda é melhor que FTP aberto, que mandaria a senha em texto)."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def conectar(host: str, usuario: str, senha: str) -> ftplib.FTP:
    ftp = FTPSLocaweb(timeout=90, context=contexto_tls())
    ftp.connect(host, 21)
    try:
        ftp.auth()
        seguro = True
    except Exception as e:  # noqa: BLE001
        print(f"O servidor não aceitou conexão criptografada ({e}).")
        seguro = False
    if seguro:
        try:
            ftp.login(usuario, senha)
        except ftplib.error_perm as e:
            sys.exit(f"Login recusado pelo servidor: {e}")
        ftp.prot_p()
        print("Conectado com criptografia (FTPS).")
        return ftp
    if not PERGUNTAR or input("Conectar sem criptografia (FTP comum, a senha trafega aberta)? [s/N] ").strip().lower() != "s":
        sys.exit("Cancelado.")
    ftp = ftplib.FTP(timeout=60)
    ftp.connect(host, 21)
    try:
        ftp.login(usuario, senha)
    except ftplib.error_perm as e:
        sys.exit(f"Login recusado pelo servidor: {e}")
    return ftp


def nomes(ftp: ftplib.FTP) -> set[str]:
    try:
        return {n.rstrip("/").split("/")[-1] for n in ftp.nlst()}
    except ftplib.error_perm:
        return set()


def ir_para_raiz_do_site(ftp: ftplib.FTP) -> set[str]:
    atual = nomes(ftp)
    if not ({"wp-config.php", "index.php"} & atual):
        for pasta in ("public_html", "www", "httpdocs"):
            if pasta in atual:
                ftp.cwd(pasta)
                atual = nomes(ftp)
                break
    if not ({"wp-config.php", "index.php"} & atual):
        sys.exit("Não achei a pasta do site (sem wp-config.php/index.php). Conteúdo da pasta atual: "
                 + ", ".join(sorted(atual)[:40]))
    print(f"Pasta do site no servidor: {ftp.pwd()}")
    return atual


def baixar(ftp: ftplib.FTP, nome: str) -> bytes | None:
    buf = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {nome}", buf.write)
    except ftplib.error_perm:
        return None
    return buf.getvalue()


def enviar(ftp: ftplib.FTP, remoto: str, dados: bytes) -> None:
    ftp.storbinary(f"STOR {remoto}", io.BytesIO(dados))


def criar_pasta(ftp: ftplib.FTP, pasta: str) -> None:
    try:
        ftp.mkd(pasta)
    except ftplib.error_perm:
        pass  # já existe


def digital(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def ler_manifesto() -> dict:
    try:
        return json.loads(MANIFESTO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar_manifesto(m: dict) -> None:
    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    MANIFESTO.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def guardar_do_servidor(ftp: ftplib.FTP, pasta: Path, atual: set[str]) -> None:
    """Cópia dos arquivos da raiz que o site novo substitui (antes de sobrescrever)."""
    for nome in ("index.html", "privacidade.html") + NA_RAIZ_TAMBEM:
        if nome in atual and not (pasta / nome).exists():
            dados = baixar(ftp, nome)
            if dados is not None:
                (pasta / nome).write_bytes(dados)


# ------------------------------------------------------------------ conferência pela internet
def baixar_url(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (publicacao WG)", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.geturl(), r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception as e:  # noqa: BLE001
        return 0, url, str(e)


def conferir(esperado_novo: bool) -> bool:
    marca = f"?v={int(time.time())}"
    st, _, corpo = baixar_url(f"https://{DOMINIO}/{marca}")
    novo = TEXTO_DO_SITE_NOVO in corpo
    st_logo, _, _ = baixar_url(LOGO_DOS_EMAILS)
    st_red, final, corpo_red = baixar_url(f"https://{DOMINIO}/contabilidade/{marca}")
    print("\nConferência pela internet:")
    print(f"  Página inicial ({st}): {'site NOVO' if novo else 'site antigo (WordPress)'}")
    print(f"  Logo dos e-mails do jornal: {'ok' if st_logo == 200 else f'ERRO {st_logo}'}")
    if esperado_novo:
        print(f"  /contabilidade/ leva para: {final} ({'ok' if TEXTO_DO_SITE_NOVO in corpo_red else 'conferir'})")
    ok = (novo == esperado_novo) and st_logo == 200
    print("  Resultado: " + ("TUDO CERTO" if ok else "algo não saiu como esperado (veja acima)"))
    return ok


# ------------------------------------------------------------------ ações
def simular() -> None:
    lista = arquivos_do_site()
    total = sum(p.stat().st_size for _, p in lista)
    print(f"Seriam enviados {len(lista)} arquivos ({total / 1024:.0f} KB) para a pasta do site:")
    for remoto, p in lista:
        print(f"  {remoto}  ({p.stat().st_size / 1024:.0f} KB)")
    print("\nE este bloco iria para o topo do .htaccess (as regras do WordPress ficam abaixo dele):\n")
    print(BLOCO_HTACCESS)
    print("Nada do WordPress é apagado. Antes de mudar, o .htaccess atual é salvo em backups_locaweb/.")


def publicar(so_paginas: bool) -> None:
    lista = arquivos_do_site()
    manifesto = ler_manifesto()
    conteudo = {remoto: local.read_bytes() for remoto, local in lista}
    if so_paginas:
        lista = [(r, l) for r, l in lista if manifesto.get(r) != digital(conteudo[r])]
        if not lista:
            print("Nada mudou desde a última publicação na Locaweb; nada para enviar.")
            return
    host, usuario, senha = credenciais()
    ftp = conectar(host, usuario, senha)
    try:
        atual = ir_para_raiz_do_site(ftp)
        wp = "wp-config.php" in atual
        print(f"WordPress nesta pasta: {'sim' if wp else 'não encontrado'} | itens na pasta: {len(atual)}")
        if "blog" in atual and not so_paginas:
            ftp.cwd("blog")
            dentro = nomes(ftp)
            ftp.cwd("..")
            estranhos = [n for n in dentro if not n.endswith(".html")]
            if estranhos:
                sys.exit(f"Já existe uma pasta blog/ no servidor com outros arquivos ({estranhos[:5]}). Nada foi alterado.")
        ht_atual = (baixar(ftp, ".htaccess") or b"").decode("utf-8", "replace")
        if so_paginas and MARCA_INI not in ht_atual:
            sys.exit("O site novo ainda não foi publicado nesta hospedagem. Rode primeiro sem --atualizar. Nada foi alterado.")
        if not so_paginas:
            print(f"\nVou enviar {len(lista)} arquivos e pôr o bloco do site novo no topo do .htaccess.")
            if PERGUNTAR and input("Publicar agora? [s/N] ").strip().lower() != "s":
                sys.exit("Cancelado. Nada foi alterado.")
            pasta = PASTA_BACKUPS / datetime.now().strftime("%Y-%m-%d_%H%M%S")
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / "htaccess_antes.txt").write_text(ht_atual, encoding="utf-8")
            (pasta / "pasta_do_site.txt").write_text(f"{ftp.pwd()}\n" + "\n".join(sorted(atual)), encoding="utf-8")
            guardar_do_servidor(ftp, pasta, atual)
            print(f"Backup salvo em {pasta}")
        criar_pasta(ftp, "blog")
        for i, (remoto, local) in enumerate(lista, 1):
            enviar(ftp, remoto, conteudo[remoto])
            manifesto[remoto] = digital(conteudo[remoto])
            print(f"  [{i}/{len(lista)}] {remoto}")
        gravar_manifesto(manifesto)
        if not so_paginas:
            enviar(ftp, ".htaccess", com_bloco(ht_atual).encode("utf-8"))
            print("  .htaccess atualizado (bloco do site novo no topo)")
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()
    time.sleep(3)
    conferir(esperado_novo=True)


def desfazer() -> None:
    host, usuario, senha = credenciais()
    ftp = conectar(host, usuario, senha)
    try:
        atual = ir_para_raiz_do_site(ftp)
        print("Vou tirar o bloco do .htaccess e apagar index.html, privacidade.html e a pasta blog/ do site novo.")
        if PERGUNTAR and input("Voltar para o WordPress agora? [s/N] ").strip().lower() != "s":
            sys.exit("Cancelado. Nada foi alterado.")
        ht = (baixar(ftp, ".htaccess") or b"").decode("utf-8", "replace")
        if MARCA_INI in ht:
            enviar(ftp, ".htaccess", tirar_bloco(ht).encode("utf-8"))
            print("  bloco removido do .htaccess")
        for nome in ("index.html", "privacidade.html"):
            if nome in atual:
                ftp.delete(nome)
                print(f"  apagado {nome}")
        # o sitemap/robots de antes do site novo: volta a cópia do 1º backup que tem o arquivo; sem cópia, ele não
        # existia antes e sai
        backups = sorted(p for p in PASTA_BACKUPS.glob("20*") if p.is_dir())
        for nome in NA_RAIZ_TAMBEM:
            copia = next((p / nome for p in backups if (p / nome).exists()), None)
            if copia is not None:
                enviar(ftp, nome, copia.read_bytes())
                print(f"  {nome} de antes devolvido")
            elif nome in atual:
                ftp.delete(nome)
                print(f"  apagado {nome}")
        if MANIFESTO.exists():
            MANIFESTO.unlink()
        if "blog" in atual:
            ftp.cwd("blog")
            for n in nomes(ftp):
                if n.endswith(".html"):
                    ftp.delete(n)
            ftp.cwd("..")
            try:
                ftp.rmd("blog")
                print("  pasta blog/ removida")
            except ftplib.error_perm as e:
                print(f"  pasta blog/ ficou (não estava vazia: {e})")
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()
    time.sleep(3)
    conferir(esperado_novo=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Publica o site novo da WG na Locaweb, ao lado do WordPress.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--simular", action="store_true", help="mostra o que seria feito, sem conectar")
    g.add_argument("--atualizar", action="store_true", help="só reenvia as páginas")
    g.add_argument("--desfazer", action="store_true", help="volta o WordPress como estava")
    ap.add_argument("--sem-perguntar", action="store_true", help="não pede confirmação (tarefa agendada)")
    a = ap.parse_args()
    global PERGUNTAR
    PERGUNTAR = not a.sem_perguntar
    if a.simular:
        simular()
    elif a.desfazer:
        desfazer()
    else:
        publicar(so_paginas=a.atualizar)


if __name__ == "__main__":
    main()
