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

## ⚠️ Por que os dados sumiam (e como isso foi corrigido)

No plano gratuito do Render, o **disco é temporário**: toda vez que o site
"dorme" (15 minutos sem uso) e acorda de novo, ele recria os arquivos do
zero — inclusive o banco de dados. Isso não é um bug do app, é assim que a
hospedagem gratuita funciona (documentação oficial do Render confirma isso).

**A solução: o banco de dados saiu do servidor e foi para um serviço
externo (Neon), que é Postgres gratuito de verdade e sem prazo de
expiração.** Agora, mesmo quando o Render dorme e recria os arquivos, o
banco continua intacto porque não está mais dentro do Render.

### Como criar seu banco no Neon (uma vez só)

1. Acesse **neon.tech** e crie uma conta grátis (dá pra entrar com GitHub)
2. Clique em **"Create a project"**, dê um nome (ex: `contador-baus`) e crie
3. Na tela do projeto, procure o **"Connection string"** — algo como
   `postgresql://usuario:senha@ep-xxxx.neon.tech/neondb?sslmode=require`
4. Copie essa string inteira

### Colocando no Render

1. No painel do seu serviço no Render, aba **"Environment"**
2. Adicione (ou edite, se já existir): `DATABASE_URL` = a string que você
   copiou do Neon
3. **Save Changes** — o Render reinicia sozinho

Pronto — agora, mesmo que o site durma e acorde depois de uma semana, os
jogadores e baús continuam lá.

**Se você já estava usando o app antes dessa correção:** infelizmente os
dados que sumiram não têm como ser recuperados (estavam só no disco
temporário do Render). A partir de agora, com o Neon configurado, isso não
acontece mais — é só recadastrar uma vez.

## Configuração (antes de rodar pela 1ª vez)

1. Copie `.env.example` para um arquivo chamado `.env`.
2. Preencha:
   - `DATABASE_URL` → veja a seção acima ("Como criar seu banco no Neon")
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

## Um app por clã (replicando para vários clãs)

Cada clã tem sua **própria cópia isolada** do app — não existe um sistema
central com "vários clãs dentro". Isso significa: banco de dados separado,
senha de admin separada, e opcionalmente até chave de API separada. Um
admin de um clã nunca vê ou mexe no que é de outro clã, porque tecnicamente
são duas instalações diferentes.

O que já preparei pra isso: uma variável `CLAN_NAME` que define o nome
mostrado no topo do site — assim cada cópia mostra o nome do seu próprio
clã, sem precisar mexer no código.

### Como criar a cópia de um novo clã

Repita o passo a passo da seção "Colocando no ar pelo celular" acima, mas:

1. No GitHub, use **"Use this template"** (se você marcar o primeiro
   repositório como template) ou simplesmente crie um **novo repositório**
   e suba os mesmos arquivos de novo — cada clã com seu próprio repositório.
2. No Render, crie um **novo Web Service** apontando pra esse novo
   repositório (não reaproveite o mesmo serviço).
3. Configure as variáveis de ambiente **desse clã**: `CLAN_NAME` (ex:
   "Clã dos Aliados"), `ADMIN_PASSWORD` própria, `SECRET_KEY` própria. A
   `ANTHROPIC_API_KEY` pode ser a mesma chave em todos os clãs (o custo
   de uso é somado na mesma conta) ou uma diferente por clã, se quiser
   controlar gasto separadamente.
4. Cada clã recebe seu próprio link (`https://clan-a.onrender.com`,
   `https://clan-b.onrender.com`, etc.) e seu próprio banco de dados —
   totalmente independentes entre si.

### Por que essa abordagem em vez de um sistema único multiclã

Um sistema multiclã (todos compartilhando o mesmo servidor e banco, com um
`clan_id` separando os dados) é mais econômico em hospedagem, mas exige
muito mais cuidado de isolamento (garantir que um admin nunca acesse dado
de outro clã por engano ou bug) e uma tela de login mais complexa. Como a
intenção aqui é cada clã ter o seu totalmente separado, replicar o app é
o caminho mais simples e mais seguro — cada cópia é autocontida e um
problema em um clã nunca afeta o outro.

## Colocando no ar pelo celular (sem precisar de computador)

Um app como esse é feito pra ficar num servidor rodando o tempo todo — não é
algo que se "instala" no celular como um app de loja. Mas dá pra colocar no
ar e usar 100% pelo navegador do celular, sem computador nenhum. É o caminho
recomendado, e o `Procfile` incluído no projeto já deixa isso pronto (testei
rodando com o comando de produção — `gunicorn app:app` — e funcionou certinho).

**1. Coloque o código no GitHub**
- Crie uma conta grátis em github.com (dá pra fazer tudo isso pelo navegador
  do celular).
- Toque em "New repository", dê um nome (ex: `contador-baus`) e crie.
- Extraia o zip no gerenciador de arquivos do celular, entre no repositório
  no site, toque em "Add file" → "Upload files" e envie os arquivos da pasta
  `totalbattle_app`.

**2. Crie a conta no Render**
- Acesse render.com pelo navegador e crie uma conta (dá pra entrar direto
  com o GitHub).
- Toque em "New" → "Web Service" e escolha o repositório que você subiu.

**3. Configure e publique**
- O Render detecta o `Procfile` sozinho e já sabe rodar com
  `gunicorn app:app`.
- Em "Environment", adicione as variáveis: `ANTHROPIC_API_KEY`,
  `ADMIN_PASSWORD`, `SECRET_KEY` (e, se quiser, `TELEGRAM_BOT_TOKEN` /
  `TELEGRAM_CHAT_ID`).
- Toque em "Create Web Service". Em poucos minutos o Render te dá um link
  público, tipo `https://contador-baus.onrender.com`.

**4. Use**
- Esse link é o que você e o clã abrem no navegador do celular — dá pra
  salvar como atalho na tela inicial (menu do navegador → "Adicionar à tela
  de início"), que fica com carinha de app.

No plano gratuito do Render (confirmado: sem cartão de crédito, 750 horas de
instância grátis por mês), o site "dorme" depois de 15 minutos sem uso e
demora cerca de 1 minuto pra acordar no próximo acesso — normal, não é erro.

*Alternativa avançada:* rodar o Python direto no seu Android via **Termux**
só faz sentido para uso individual (sem o resto do clã acessando de fora),
já que exigiria manter o celular ligado e um túnel público — mais técnico e
menos estável que hospedar. Não é o que recomendo como primeira opção.

Outro caminho possível: **servidor próprio (VPS)** — mais controle, mas
exige mais conhecimento técnico (configurar domínio, HTTPS, etc.) e
geralmente tem custo mensal.

**Sobre o PythonAnywhere:** eu tinha sugerido antes, mas o plano gratuito de
lá mudou — hoje o app web grátis expira depois de 1 mês, e as conexões de
saída ficam restritas a uma lista de sites liberados, o que bloquearia
justamente as chamadas para a API da Anthropic e do Telegram que esse app
precisa fazer. Por isso não é uma boa opção gratuita pra esse projeto.

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

## Recursos extras já incluídos

- **Nível e meta por jogador**: cada jogador pode ter um nível (G1 a G10, ou
  "Meta") cadastrado em "Jogadores". Em "Metas" (admin), você define quantos
  pontos cada nível precisa bater por ciclo. No ranking, quem bateu a meta
  do próprio nível aparece com "✅ Concluído"; quem não bateu, aparece
  "Faltam X" pontos.
- **Ciclos automáticos de 7 dias**: o ranking sempre conta só os baús do
  ciclo atual, que começa **todo domingo às 14h de horário de Brasília**
  (testei o cálculo com vários horários de borda — funciona certinho mesmo
  em cima da hora exata da virada). Quando um ciclo termina, ele é
  arquivado sozinho — não precisa clicar em nada, isso acontece
  automaticamente na primeira visita ao site depois da virada.
- **Histórico de ciclos anteriores, aberto pra todo mundo**: a aba "📅 Semanas"
  agora não exige login — qualquer jogador pode ver o ranking de semanas
  passadas. Clicando numa semana, mostra o ranking completo daquele ciclo.
  E na página de cada jogador (clique no nome dele no ranking), tem uma
  tabela "Histórico de ciclos anteriores" só com os pontos daquele jogador
  ao longo do tempo.
- **Envio múltiplo de prints**: em "Enviar print de baús", dá pra selecionar
  vários arquivos de uma vez — cada um é processado e lançado automaticamente.
- **Cadastrar jogadores só pelo print da lista do clã**: em "Cadastrar por
  print" (menu superior), sobe o print da tela "Meu clã" e cada nome vira um
  jogador cadastrado, sem precisar que ele já tenha coletado algum baú.
- **Exportar CSV**: botão "⬇️ baixar CSV" na página de ranking (para qualquer
  pessoa) e por semana arquivada em "Semanas" (admin).
- **Fechamento semanal**: em "Semanas" (admin), dá pra fechar o período atual
  a qualquer momento — o ranking daquele momento fica congelado no histórico,
  e a contagem reinicia do zero pro próximo período. O histórico de baús em
  si nunca é apagado, só o ranking "atual" que reseta.
- **Notificação no Telegram** quando um baú raro/épico/heroico é coletado:
  opcional, só liga se você preencher `TELEGRAM_BOT_TOKEN` e
  `TELEGRAM_CHAT_ID` no `.env` (veja abaixo como conseguir esses dois
  valores). Sem eles, o app funciona normalmente e essa parte fica desligada
  sem gerar erro.

### Como ligar a notificação do Telegram (opcional)

1. No Telegram, fale com **@BotFather**, mande `/newbot` e siga as
   instruções — ele te dá um token (`TELEGRAM_BOT_TOKEN`).
2. Adicione esse bot num grupo (ou fale com ele direto) e descubra o
   `chat_id`: mande uma mensagem qualquer pro bot e acesse
   `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no navegador — o
   `chat.id` aparece na resposta.
3. Preencha os dois valores no `.env` e reinicie o app.

## Próximos passos possíveis (ainda não construídos)

- Múltiplos administradores com login individual (hoje é uma senha única)
- Notificação por WhatsApp (exige uma API paga, tipo Twilio ou WhatsApp
  Business API — o Telegram foi escolhido primeiro por ser gratuito e simples)
- Gráfico de evolução do clã ao longo das semanas arquivadas

Se quiser evoluir esse projeto com mais profundidade — multiadmin, WhatsApp,
hospedagem definitiva rodando de verdade — o **Claude Code** é a ferramenta
ideal para continuar, já que ele trabalha diretamente no seu ambiente de
desenvolvimento e consegue rodar, testar e ajustar o servidor de forma
persistente, coisa que eu não consigo fazer sozinho depois que essa
conversa terminar.
