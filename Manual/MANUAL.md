# Contador de Baús do Clã — Manual de Funcionamento

Este é o app que substitui o processo manual de mandar prints no chat: agora o
próprio administrador sobe o print direto no sistema, que lê a imagem, identifica
jogador e tipo de baú, e atualiza o ranking automaticamente.

## O que foi construído (e o que ainda depende de você)

**Já está pronto e testado:**
- Site com ranking público (qualquer pessoa do clã pode ver, sem login)
- Login de administrador (senha única)
- Upload de print → extração automática via IA → lançamento no banco de dados
- Cadastro/remoção de jogadores
- Definição de pontos por tipo de baú
- Banco de dados próprio (SQLite), sem depender mais da planilha do Google

**Depende de você para funcionar de verdade:**
- Uma **chave de API da Anthropic** (é o "cérebro" que lê os prints) — sem ela,
  o app roda, mas o botão de upload dá erro.
- Um **lugar para hospedar** o app (ele foi testado rodando localmente; para
  ficar disponível 24h no celular do clã, precisa estar hospedado em algum
  servidor — veja a seção "Colocando no ar").

Ou seja: o código funciona e foi testado ponta a ponta (login, cadastro,
pontuação, ranking). A única parte que não testei de verdade é a leitura de
print, porque isso exige uma chave de API que só você pode gerar e que eu não
tenho acesso permanente para guardar em seu nome.

## Estrutura dos arquivos

```
totalbattle_app/
├── app.py              → as páginas e rotas do site
├── database.py         → tudo que mexe no banco de dados
├── vision.py           → a função que conversa com a IA para ler o print
├── templates/          → as telas (HTML)
├── static/style.css    → visual do site
├── requirements.txt    → lista de bibliotecas Python necessárias
├── .env.example        → modelo de configuração (copie para ".env")
└── clan.db             → banco de dados (criado automaticamente no 1º uso)
```

## Configuração (antes de rodar pela 1ª vez)

1. Copie `.env.example` para um arquivo chamado `.env`.
2. Preencha:
   - `ANTHROPIC_API_KEY` → pegue em https://console.anthropic.com (crie uma
     conta, gere uma chave em "API Keys"). Isso tem custo por uso, cobrado da
     sua conta Anthropic — cada print processado consome uma fração de centavo.
   - `ADMIN_PASSWORD` → a senha que só você vai usar para entrar como admin.
   - `SECRET_KEY` → qualquer texto aleatório (protege a sessão de login).

## Rodando localmente (para testar no seu computador)

```bash
cd totalbattle_app
pip install -r requirements.txt
python app.py
```

Abra `http://localhost:5000` no navegador. O ranking aparece direto; para
acessar upload/jogadores/pontuação, clique em "Login admin".

## Colocando no ar (para o clã acessar pelo celular)

Rodando localmente, só funciona no seu computador. Para todo mundo do clã
acessar pelo celular, o app precisa estar hospedado. Três caminhos comuns,
do mais simples ao mais robusto:

1. **Render.com ou Railway.app** (gratuito para começar): conecte o código
   (via GitHub), configure as 3 variáveis de ambiente do `.env` no painel
   deles, e a plataforma te dá um link público (`https://seu-app.onrender.com`).
2. **PythonAnywhere**: parecido, focado em Python/Flask, também tem plano
   gratuito.
3. **Servidor próprio (VPS)**: mais controle, mas exige mais conhecimento
   técnico (configurar domínio, HTTPS, etc.).

Recomendo a opção 1 para começar — é a que exige menos passos técnicos.

## Fluxo de uso no dia a dia (depois de no ar)

1. Você (admin) tira o print da tela "Baús de presente" no jogo.
2. Entra no site → Login admin → "Enviar print".
3. Sobe a imagem → o sistema mostra na tela quais baús/jogadores identificou
   e já lança no banco.
4. Qualquer pessoa do clã acessa o link do ranking (sem precisar de senha)
   e vê a pontuação atualizada.
5. Se aparecer um jogador novo (que ainda não estava cadastrado), o sistema
   cadastra ele automaticamente ao lançar o primeiro baú.
6. Jogador que saiu do clã: vá em "Jogadores" → "Remover do clã" (ele some
   do ranking, mas o histórico dele fica salvo no banco).
7. Pontuação por tipo de baú (a "Fonte", tipo "Level 25 Citadel"): defina
   em "Pontuação" — isso continua sendo decisão manual sua, como já era.

## Limitações conhecidas

- A extração de imagem depende da qualidade do print — cortar o "De:" ou a
  "Fonte:" faz o sistema simplesmente ignorar aquele card (por segurança,
  ele prefere não incluir um evento do que inventar dados).
- O servidor incluído (`python app.py`) é de desenvolvimento — para uso
  real e contínuo, a hospedagem (seção acima) já cuida disso com um
  servidor apropriado.
- Não existe (ainda) tela de login para membros comuns verem algo diferente
  do ranking público — como combinado, só o admin edita qualquer coisa.

## Próximos passos possíveis

- Exportar o ranking em Excel/CSV com um clique
- Notificação automática (Telegram/WhatsApp) quando um baú épico ou raro
  for coletado
- Histórico semanal automático (zerar ranking toda segunda-feira, por ex.)

Se quiser evoluir esse projeto com mais profundidade — múltiplos admins,
notificações, hospedagem definitiva — o **Claude Code** é a ferramenta ideal
para continuar, já que ele trabalha diretamente no seu ambiente de
desenvolvimento e consegue rodar, testar e ajustar o servidor de verdade,
coisa que eu não consigo fazer permanentemente por aqui.
