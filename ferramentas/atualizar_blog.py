"""Atualiza o blog do site com as notícias do WG Jornal (o jornal do HUB).

O que faz, a cada execução:
  1. Lê os cadernos do jornal (wg_jornal_*.json) na pasta do jornal.
  2. Acrescenta as notícias novas ao arquivo blog/artigos.json (as antigas ficam; nada é apagado).
  3. Gera blog/index.html e uma página por notícia (blog/<slug>.html), no visual do site.
  4. Atualiza a seção "Blog" da página inicial com as notícias mais recentes.

Uso (na pasta do site):  python ferramentas/atualizar_blog.py
Outra pasta do jornal:   python ferramentas/atualizar_blog.py "C:\\caminho\\para\\o\\jornal"
Depois de rodar, envie ao GitHub (git add/commit/push) ou use ferramentas/atualizar_blog.bat.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ----------------------------------------------------------------- configuração
RAIZ = Path(__file__).resolve().parent.parent
PASTA_JORNAL = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WG_PASTA_JORNAL", r"N:\Departamentos\AUTOMAÇÃO\Claude\Jornal"))
ARQUIVO_ARTIGOS = RAIZ / "blog" / "artigos.json"
PASTA_BLOG = RAIZ / "blog"
INDEX = RAIZ / "index.html"

# caderno do jornal -> nome da editoria no blog (tire daqui o que não deve ir para o site)
CADERNOS = {
    "diretoria": "Economia e negócios",
    "tributario": "Tributário",
    "fiscal": "Fiscal",
    "contabil": "Contábil",
    "pessoal": "Trabalhista",
    "financeiro": "Financeiro",
    "legalizacao": "Empresas",
    "automacao": "Tecnologia",
}
WHATSAPP = "https://api.whatsapp.com/send?phone=5519997816418&text=" + quote("Olá! Vim pelo blog do site e quero falar com um especialista.")
NA_INICIAL = 4          # 1 destaque + 3 na lista da página inicial
SITE = "https://wgcontabilidade.com.br"   # endereço oficial: canonical, og:url e sitemap.xml (o GitHub Pages é espelho)
ARQUIVO_SITEMAP = RAIZ / "sitemap.xml"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


# ----------------------------------------------------------------- utilidades
def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80].rstrip("-") or "artigo"


def data_br(d: str) -> datetime | None:
    try:
        return datetime.strptime(d.strip()[:10], "%d/%m/%Y")
    except ValueError:
        return None


def data_extenso(d: str) -> str:
    dt = data_br(d)
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}" if dt else d


def iso(d: str) -> str:
    dt = data_br(d)
    return dt.strftime("%Y-%m-%d") if dt else ""


def esc(t: str) -> str:
    return html.escape(t or "", quote=True)


def paragrafos(texto: str) -> list[str]:
    blocos = [b.strip() for b in re.split(r"\n\s*\n", texto or "") if b.strip()]
    return [re.sub(r"\s*\n\s*", " ", b) for b in blocos]


# ----------------------------------------------------------------- 1. ler o jornal e acumular
def carregar_artigos() -> list[dict]:
    if ARQUIVO_ARTIGOS.exists():
        return json.loads(ARQUIVO_ARTIGOS.read_text(encoding="utf-8"))
    return []


def chave(t: dict) -> str:
    link = (t.get("link") or "").strip().lower().rstrip("/")
    if link:
        return "link:" + link
    return "titulo:" + slugify(t.get("titulo", ""))


def ler_jornal(artigos: list[dict]) -> int:
    conhecidas = {chave(a) for a in artigos}
    slugs = {a["slug"] for a in artigos}
    novos = 0
    if not PASTA_JORNAL.exists():
        print(f"AVISO: pasta do jornal não encontrada: {PASTA_JORNAL} (o blog é gerado só com o que já está em artigos.json)")
        return 0
    for caderno, editoria in CADERNOS.items():
        arq = PASTA_JORNAL / f"wg_jornal_{caderno}.json"
        if not arq.exists():
            continue
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"AVISO: não consegui ler {arq.name}: {e}")
            continue
        edicao = str(dados.get("data", "")).strip()
        for t in dados.get("topicos") or []:
            if not isinstance(t, dict) or not t.get("titulo"):
                continue
            k = chave(t)
            if k in conhecidas:
                continue
            slug = slugify(t["titulo"])
            if slug in slugs:
                slug = f"{slug}-{iso(edicao) or datetime.now().strftime('%Y-%m-%d')}"
            artigos.append({
                "chave": k, "slug": slug,
                "titulo": str(t.get("titulo", "")).strip(),
                "resumo": str(t.get("resumo", "")).strip(),
                "texto": str(t.get("texto", "")).strip(),
                "fonte": str(t.get("fonte", "")).strip(),
                "link": str(t.get("link", "")).strip(),
                "publicado_em": str(t.get("publicado_em", "")).strip()[:10] or edicao,
                "edicao": edicao,
                "caderno": caderno, "editoria": editoria,
                "adicionado_em": datetime.now().isoformat(timespec="seconds"),
            })
            conhecidas.add(k)
            slugs.add(slug)
            novos += 1
    return novos


def ordenar(artigos: list[dict]) -> list[dict]:
    return sorted(artigos, key=lambda a: (iso(a.get("publicado_em", "")) or iso(a.get("edicao", "")), a.get("adicionado_em", "")), reverse=True)


# ----------------------------------------------------------------- 2. pedaços do site reaproveitados
def pedacos_do_site(indice: str, prefixo: str = "../") -> dict:
    """Estilo, cabeçalho e rodapé da página inicial, com os links ajustados para uma página
    em outra pasta (prefixo "../", caso do blog) ou na raiz (prefixo "./")."""
    estilo = re.search(r"<style>.*?</style>", indice, re.S).group(0)
    cabeca = indice[: indice.index("</head>")]
    links = "\n".join(l for l in re.findall(r"^<link[^>]*>$", cabeca, re.M) if 'rel="canonical"' not in l)
    header = re.search(r"<header class=\"nav\".*?</header>", indice, re.S).group(0)
    footer = re.search(r"<footer.*?</footer>", indice, re.S).group(0)

    def ajustar(bloco: str) -> str:
        if prefixo == "../":
            bloco = bloco.replace('href="blog/"', 'href="./"')
        bloco = bloco.replace('href="#topo"', f'href="{prefixo}"')
        bloco = re.sub(r'href="#([^"]+)"', lambda m: f'href="{prefixo}#{m.group(1)}"', bloco)
        # outros caminhos relativos da raiz (ex.: privacidade.html)
        bloco = re.sub(r'href="(?!https?:|#|\.\./|\./|mailto:|tel:|data:)([^"]+)"', lambda m: f'href="{prefixo}{m.group(1)}"', bloco)
        if prefixo == "../":
            bloco = bloco.replace('<a href="../#blog">Blog</a>', '<a href="./" class="is-current">Blog</a>')
        return bloco

    return {"estilo": estilo, "links": links, "header": ajustar(header), "footer": ajustar(footer)}


CSS_BLOG = """
<style>
/* ---- blog ---- */
.pagina{padding-top:84px}
.pagina .sec{padding-block:64px 96px}
.blog-head{max-width:760px;margin:0 auto 40px;text-align:center}
.blog-head h1{font-size:clamp(2rem,1.4rem+2vw,3rem);line-height:1.1;margin:0 0 14px}
.cartao .editoria,.artigo-topo .editoria{align-self:flex-start}
.editoria{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;border:1px solid rgba(14,133,133,.35);border-radius:999px;background:var(--paper);font-size:.66rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--teal-d)}
.editoria::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--teal)}
.filtros{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:0 0 36px;padding:0;list-style:none}
.filtros button{padding:8px 14px;border:1px solid var(--line-2);border-radius:999px;background:var(--panel);font:inherit;font-size:.8rem;font-weight:600;color:var(--muted);cursor:pointer}
.filtros button.is-on{background:var(--teal);border-color:var(--teal);color:#fff}
.blog-lista{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px;margin:0;padding:0;list-style:none}
.blog-lista li[hidden]{display:none}
.cartao{display:flex;flex-direction:column;gap:12px;height:100%;padding:24px 24px 26px;border:1px solid var(--line);border-radius:18px;background:var(--panel);color:inherit;text-decoration:none;transition:transform .25s,box-shadow .25s,border-color .25s}
.cartao:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(22,33,31,.08);border-color:rgba(14,133,133,.35)}
.cartao h3{margin:0;font-size:1.08rem;line-height:1.3}
.cartao p{margin:0;font-size:.92rem;color:var(--muted)}
.cartao .more{margin-top:auto;padding-top:6px}
.artigo{max-width:760px;margin:0 auto}
.artigo-topo{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px;margin-bottom:18px}
.artigo h1{margin:0 0 16px;font-size:clamp(1.7rem,1.2rem+1.8vw,2.5rem);line-height:1.15;letter-spacing:-.02em}
.artigo-lead{margin:0 0 28px;font-size:1.12rem;line-height:1.55;color:var(--muted)}
.artigo-corpo p{margin:0 0 18px;font-size:1.02rem;line-height:1.75}
.artigo-corpo h2{margin:30px 0 10px;font-size:1.25rem;line-height:1.3}
.fonte-box{margin:32px 0 0;padding:16px 20px;border-left:3px solid var(--teal);background:var(--panel);border-radius:0 12px 12px 0;font-size:.9rem;color:var(--muted)}
.fonte-box a{color:var(--teal-d);font-weight:600;word-break:break-all}
.cta-box{margin:44px 0 0;padding:30px 28px;border-radius:20px;background:var(--teal);color:#fff;text-align:center}
.cta-box h2{margin:0 0 8px;font-size:1.3rem}
.cta-box p{margin:0 0 18px;color:rgba(255,255,255,.85)}
.cta-box .btn{background:#fff;color:var(--teal-d)}
.leia-tambem{margin-top:56px}
.leia-tambem h2{font-size:1.1rem;margin:0 0 16px}
.voltar{display:inline-flex;align-items:center;gap:8px;margin-bottom:26px;font-size:.85rem;font-weight:700;color:var(--teal-d);text-decoration:none}
@media (max-width:1024px){.blog-lista{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:680px){.pagina{padding-top:96px}.blog-lista{grid-template-columns:1fr}.sec{padding-block:56px}}
</style>
"""

JS_BLOG = """
<script>
(function(){
  var t=document.querySelector('.nav-toggle'),n=document.getElementById('nav-links'),h=document.getElementById('nav');
  if(h){var r=function(){h.classList.toggle('is-scrolled',window.scrollY>8);};window.addEventListener('scroll',r,{passive:true});r();}
  if(t&&n){
    t.addEventListener('click',function(){var o=n.classList.toggle('is-open');t.setAttribute('aria-expanded',String(o));t.setAttribute('aria-label',o?'Fechar menu':'Abrir menu');});
    n.addEventListener('click',function(e){if(e.target.closest('a'))n.classList.remove('is-open');});
  }
  document.querySelectorAll('[data-year]').forEach(function(e){e.textContent=new Date().getFullYear();});
  var fs=document.querySelectorAll('.filtros button'),cs=document.querySelectorAll('.blog-lista li');
  fs.forEach(function(b){b.addEventListener('click',function(){
    fs.forEach(function(x){x.classList.toggle('is-on',x===b);});
    cs.forEach(function(c){c.hidden=b.dataset.f!=='todos'&&c.dataset.editoria!==b.dataset.f;});
  });});
})();
</script>
"""


def pagina(p: dict, titulo: str, descricao: str, corpo: str, caminho: str | None = None) -> str:
    """`caminho` = endereço da página a partir da raiz do site (ex.: "blog/x.html"); vira o canonical e o og:url,
    para o Google tratar o domínio oficial como o original (e não o espelho do GitHub Pages)."""
    oficial = ""
    if caminho is not None:
        oficial = f'<link rel="canonical" href="{SITE}/{caminho}">\n<meta property="og:url" content="{SITE}/{caminho}">\n'
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<meta name="theme-color" content="#F4F6F5">
<meta property="og:type" content="article">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
{oficial}{p['links']}
{p['estilo']}
{CSS_BLOG}
</head>
<body>
{p['header']}
<main class="pagina">
{corpo}
</main>
{p['footer']}
{JS_BLOG}
</body>
</html>
"""


# ----------------------------------------------------------------- 3. páginas do blog
def cartao(a: dict) -> str:
    return (
        f'<li data-editoria="{esc(a["editoria"])}">\n'
        f'  <a class="cartao" href="{a["slug"]}.html">\n'
        f'    <span class="editoria">{esc(a["editoria"])}</span>\n'
        f'    <span class="post-date">{esc(data_extenso(a["publicado_em"]))}</span>\n'
        f'    <h3>{esc(a["titulo"])}</h3>\n'
        f'    <p>{esc(a["resumo"])}</p>\n'
        f'    <span class="more">Ler notícia <i>→</i></span>\n'
        f'  </a>\n</li>'
    )


def gerar_indice(p: dict, artigos: list[dict]) -> None:
    editorias = []
    for a in artigos:
        if a["editoria"] not in editorias:
            editorias.append(a["editoria"])
    filtros = '<li><button type="button" class="is-on" data-f="todos">Todas</button></li>' + "".join(
        f'<li><button type="button" data-f="{esc(e)}">{esc(e)}</button></li>' for e in editorias)
    corpo = f"""<section class="band band--white">
  <div class="wrap sec">
    <div class="blog-head">
      <p class="eyebrow center">Blog · WG Jornal</p>
      <h1>Conteúdo para decidir melhor.</h1>
      <p class="section-sub">As notícias que importam para a sua empresa, selecionadas todos os dias pela equipe da WG a partir das fontes oficiais e da imprensa especializada.</p>
    </div>
    <ul class="filtros" aria-label="Filtrar por editoria">{filtros}</ul>
    <ul class="blog-lista">
{chr(10).join(cartao(a) for a in artigos)}
    </ul>
  </div>
</section>"""
    (PASTA_BLOG / "index.html").write_text(
        pagina(p, "Blog | WG Contabilidade", "Notícias contábeis, fiscais, trabalhistas e tributárias selecionadas todos os dias pela WG Contabilidade.", corpo,
               caminho="blog/"),
        encoding="utf-8", newline="\n")


def gerar_artigo(p: dict, a: dict, outros: list[dict]) -> None:
    corpo_txt = "".join(f"<p>{esc(x)}</p>\n" for x in paragrafos(a["texto"])) or f"<p>{esc(a['resumo'])}</p>\n"
    fonte = ""
    if a.get("fonte") or a.get("link"):
        link = f' — <a href="{esc(a["link"])}" target="_blank" rel="noopener nofollow">ler a notícia original</a>' if a.get("link") else ""
        fonte = f'<p class="fonte-box">Fonte: {esc(a.get("fonte") or "imprensa especializada")}{link}. Resumo e comentário da equipe da WG Contabilidade; edição do WG Jornal de {esc(a.get("edicao", ""))}.</p>'
    leia = ""
    if outros:
        leia = '<section class="leia-tambem"><h2>Leia também</h2><ul class="blog-lista">' + "".join(cartao(o) for o in outros) + "</ul></section>"
    corpo = f"""<section class="band band--white">
  <div class="wrap sec">
    <article class="artigo">
      <a class="voltar" href="./">← Voltar ao blog</a>
      <div class="artigo-topo">
        <span class="editoria">{esc(a["editoria"])}</span>
        <span class="post-date">{esc(data_extenso(a["publicado_em"]))}</span>
      </div>
      <h1>{esc(a["titulo"])}</h1>
      <p class="artigo-lead">{esc(a["resumo"])}</p>
      <div class="artigo-corpo">
{corpo_txt}      </div>
      {fonte}
      <div class="cta-box">
        <h2>Isso mexe com a sua empresa?</h2>
        <p>Fale com a equipe da WG e veja o que muda na prática para o seu negócio.</p>
        <a class="btn btn-lg" href="{WHATSAPP}" target="_blank" rel="noopener">Falar no WhatsApp</a>
      </div>
    </article>
    {leia}
  </div>
</section>"""
    (PASTA_BLOG / f"{a['slug']}.html").write_text(
        pagina(p, f"{a['titulo']} | Blog WG Contabilidade", a["resumo"], corpo, caminho=f"blog/{a['slug']}.html"),
        encoding="utf-8", newline="\n")


# ----------------------------------------------------------------- 4. seção da página inicial
def atualizar_inicial(indice: str, artigos: list[dict]) -> str:
    inicio = indice.index('<div class="blog-grid">')
    fim = indice.index("\n    </div>\n  </div>\n</section>", inicio) + len("\n    </div>")
    atual = indice[inicio:fim]
    arte = re.search(r'<div class="post-art" aria-hidden="true">.*?</svg>\s*</div>', atual, re.S)
    arte = arte.group(0) if arte else ""
    # na página inicial, as editorias mais ligadas ao dia a dia das empresas vêm primeiro
    prioridade = {c: i for i, c in enumerate(["diretoria", "tributario", "fiscal", "pessoal", "contabil", "financeiro", "legalizacao", "automacao"])}
    recentes = artigos[:12]
    recentes = sorted(recentes, key=lambda a: (prioridade.get(a["caderno"], 99), -int((iso(a["publicado_em"]) or "0").replace("-", "") or 0)))
    destaque, lista = recentes[0], recentes[1:NA_INICIAL]
    linhas = ""
    for i, a in enumerate(lista):
        atraso = f' style="--delay:{110 * i}ms"' if i else ""
        linhas += (f'        <a class="post-row reveal" data-anim="right"{atraso} href="blog/{a["slug"]}.html">\n'
                   f'          <span class="post-date">{esc(data_extenso(a["publicado_em"]))}</span>\n'
                   f'          <b>{esc(a["titulo"])}</b>\n        </a>\n')
    novo = f"""<div class="blog-grid">
      <a class="post-feature reveal" data-anim="left" href="blog/{destaque["slug"]}.html">
        {arte}
        <div class="post-body">
          <span class="post-date">{esc(data_extenso(destaque["publicado_em"]))} · {esc(destaque["editoria"])}</span>
          <h3>{esc(destaque["titulo"])}</h3>
          <p class="post-excerpt">{esc(destaque["resumo"])}</p>
          <span class="more" style="padding-top:6px">Ler notícia <i>→</i></span>
        </div>
      </a>

      <div class="post-list">
{linhas}        <a class="post-all" href="blog/">Ver todas as notícias
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </a>
      </div>
    </div>"""
    return indice[:inicio] + novo + indice[fim:]


# ----------------------------------------------------------------- 5. "Leia também" e sitemap.xml
def entrada(a: dict) -> tuple[str, str]:
    """Ordem em que a notícia entrou no blog (artigos.json só cresce)."""
    return (a.get("adicionado_em", ""), a.get("slug", ""))


def leia_tambem(a: dict, artigos: list[dict]) -> list[dict]:
    """Até 3 notícias que entraram no blog ANTES desta, as mais recentes, da mesma editoria primeiro.
    Só as anteriores: quando chegam notícias novas, as páginas antigas continuam iguais, e a atualização diária
    sobe só as páginas novas (e não o blog inteiro) para o GitHub e para a Locaweb."""
    k = entrada(a)
    mesma, outras = [], []
    for o in artigos:                                   # artigos já vem da mais nova para a mais antiga
        if o is a or entrada(o) >= k:
            continue
        if o["editoria"] == a["editoria"]:
            mesma.append(o)
            if len(mesma) == 3:
                break
        elif len(outras) < 3:
            outras.append(o)
    return (mesma + outras)[:3]


def gerar_sitemap(artigos: list[dict]) -> None:
    """sitemap.xml do domínio oficial: página inicial, blog, privacidade e cada notícia. A data da página inicial e
    do blog é a da notícia mais recente (assim o arquivo só muda quando entra notícia nova)."""
    ultima = max((iso(a.get("publicado_em", "")) or iso(a.get("edicao", "")) for a in artigos), default="")
    urls = [(f"{SITE}/", ultima), (f"{SITE}/blog/", ultima), (f"{SITE}/privacidade.html", "")]
    urls += [(f"{SITE}/blog/{a['slug']}.html", iso(a.get("publicado_em", "")) or iso(a.get("edicao", ""))) for a in artigos]
    linhas = "".join(
        f"  <url><loc>{esc(u)}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>\n" for u, d in urls)
    ARQUIVO_SITEMAP.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + linhas + "</urlset>\n",
                               encoding="utf-8", newline="\n")


# ----------------------------------------------------------------- principal
def main() -> None:
    PASTA_BLOG.mkdir(exist_ok=True)
    artigos = carregar_artigos()
    novos = ler_jornal(artigos)
    artigos = ordenar(artigos)
    if not artigos:
        print("Nenhuma notícia para publicar.")
        return
    ARQUIVO_ARTIGOS.write_text(json.dumps(artigos, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    indice = INDEX.read_text(encoding="utf-8")
    p = pedacos_do_site(indice)
    gerar_indice(p, artigos)
    for a in artigos:
        gerar_artigo(p, a, leia_tambem(a, artigos))
    gerar_sitemap(artigos)
    INDEX.write_text(atualizar_inicial(indice, artigos), encoding="utf-8", newline="\n")
    print(f"Blog atualizado: {novos} notícia(s) nova(s), {len(artigos)} no total. Páginas em {PASTA_BLOG}.")


if __name__ == "__main__":
    main()
