"""Gera a página privacidade.html (Política de Privacidade) no visual do site.

Uso (na pasta do site):  python ferramentas/gerar_privacidade.py
O texto fica neste arquivo; depois de alterar, rode de novo para regerar a página.
"""
from pathlib import Path

from atualizar_blog import INDEX, RAIZ, WHATSAPP, pagina, pedacos_do_site

ATUALIZADA_EM = "9 de novembro de 2026"

CORPO = f"""<section class="band band--white">
  <div class="wrap sec">
    <article class="artigo">
      <div class="artigo-topo">
        <span class="editoria">Política de Privacidade</span>
        <span class="post-date">Atualizada em {ATUALIZADA_EM}</span>
      </div>
      <h1>Como a WG Contabilidade trata os seus dados</h1>
      <p class="artigo-lead">Esta política explica quais dados pessoais passam por este site e pelo escritório, para que servem, com quem são compartilhados e quais são os seus direitos, conforme a Lei Geral de Proteção de Dados (Lei nº 13.709/2018, a LGPD).</p>

      <div class="artigo-corpo">
        <h2>1. Quem é o responsável</h2>
        <p>O controlador dos dados é a <strong>WG Contabilidade</strong>, escritório contábil estabelecido na Rua Dr. Sales de Oliveira, 809, Vila Industrial, Campinas-SP. Para qualquer assunto sobre dados pessoais, fale conosco pelos canais indicados no fim desta página.</p>

        <h2>2. Dados tratados neste site</h2>
        <p>Este site é informativo e <strong>não possui formulários nem área de login</strong>: nenhum dado é digitado ou armazenado aqui. Ao navegar, alguns dados técnicos são tratados automaticamente:</p>
        <p><strong>Registros de acesso.</strong> O provedor que hospeda o site pode registrar o endereço IP, a data e a hora do acesso, o navegador e as páginas visitadas, para fins de segurança e funcionamento, conforme a política de privacidade do próprio provedor.</p>
        <p><strong>Fontes tipográficas.</strong> As fontes das páginas são carregadas dos servidores do Google (Google Fonts). Ao abrir o site, o seu navegador envia o endereço IP ao Google para baixar esses arquivos.</p>
        <p><strong>Cookies.</strong> O site não instala cookies próprios nem usa ferramentas de rastreamento ou publicidade.</p>

        <h2>3. Quando você fala com a gente</h2>
        <p>Os botões de contato abrem o <strong>WhatsApp</strong> ou a ligação telefônica. Ao usar esses canais, você nos envia o seu nome, o seu número e o conteúdo da mensagem. Usamos essas informações apenas para responder ao seu contato, enviar a proposta pedida e, se você virar cliente, prestar os serviços contratados. As conversas pelo WhatsApp também estão sujeitas à política de privacidade da Meta, responsável pelo aplicativo.</p>

        <h2>4. Dados dos clientes do escritório</h2>
        <p>Na prestação dos serviços contábeis, fiscais, trabalhistas e de consultoria, a WG trata dados pessoais de sócios, funcionários e contatos das empresas clientes (como nome, CPF, dados cadastrais, salariais e bancários). Esse tratamento tem como bases legais a <strong>execução do contrato</strong> com o cliente e o <strong>cumprimento de obrigações legais e regulatórias</strong> perante a Receita Federal, o eSocial, a Junta Comercial e demais órgãos. Os dados ficam guardados pelos prazos exigidos pela legislação contábil, fiscal e trabalhista, que em geral é de cinco anos ou mais após o fato, e são compartilhados somente com os órgãos públicos e sistemas necessários à prestação do serviço.</p>

        <h2>5. Com quem compartilhamos</h2>
        <p>Não vendemos nem cedemos dados pessoais a terceiros. O compartilhamento acontece apenas: com órgãos públicos, por obrigação legal; com fornecedores de tecnologia que operam os nossos sistemas, sempre sob contrato e com as medidas de segurança adequadas; e quando houver determinação judicial ou de autoridade competente.</p>

        <h2>6. Links para outros sites</h2>
        <p>O site contém links para o WhatsApp, redes sociais (Instagram, LinkedIn e Facebook) e para a plataforma de BI da WG. Ao acessá-los, valem as políticas de privacidade de cada um desses serviços.</p>

        <h2>7. Segurança</h2>
        <p>Adotamos medidas técnicas e administrativas para proteger os dados contra acessos não autorizados, perda ou alteração indevida, como controle de acesso por usuário, certificados digitais, cópias de segurança e orientação da equipe. Nenhum sistema é totalmente seguro; se identificarmos um incidente que possa trazer risco relevante a você, comunicaremos os envolvidos e a Autoridade Nacional de Proteção de Dados (ANPD), conforme a lei.</p>

        <h2>8. Os seus direitos</h2>
        <p>Você pode, a qualquer momento, pedir a confirmação de que tratamos os seus dados, o acesso a eles, a correção de dados incompletos ou desatualizados, a anonimização, o bloqueio ou a eliminação de dados desnecessários, a portabilidade, a informação sobre compartilhamentos e a revogação do consentimento, quando o tratamento se basear nele. Os pedidos são atendidos nos prazos da LGPD; alguns dados podem ser mantidos quando a lei exigir a sua guarda.</p>

        <h2>9. Como falar sobre privacidade</h2>
        <p>Para exercer os seus direitos ou tirar dúvidas sobre esta política, fale com a WG Contabilidade pelo WhatsApp, pelo telefone <a href="tel:+5519997816418">+55 19 99781-6418</a> ou pessoalmente no endereço acima, de segunda a quinta, das 8h às 18h, e na sexta, das 8h às 17h.</p>

        <h2>10. Alterações desta política</h2>
        <p>Esta política pode ser atualizada para refletir mudanças na legislação ou nos nossos serviços. A versão em vigor é sempre a publicada nesta página, com a data de atualização indicada no topo.</p>
      </div>

      <div class="cta-box">
        <h2>Dúvidas sobre os seus dados?</h2>
        <p>Fale com a equipe da WG. Respondemos no horário comercial.</p>
        <a class="btn btn-lg" href="{WHATSAPP}" target="_blank" rel="noopener">Falar no WhatsApp</a>
      </div>
    </article>
  </div>
</section>"""


def main() -> None:
    indice = INDEX.read_text(encoding="utf-8")
    p = pedacos_do_site(indice, prefixo="./")
    destino = RAIZ / "privacidade.html"
    destino.write_text(
        pagina(p, "Política de Privacidade | WG Contabilidade",
               "Como a WG Contabilidade trata os dados pessoais de quem visita o site e dos clientes do escritório, conforme a LGPD.",
               CORPO),
        encoding="utf-8", newline="\n")
    print("gerado:", destino.name)


if __name__ == "__main__":
    main()
