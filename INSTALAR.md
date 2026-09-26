# Instalando o Vertex ERP numa máquina nova

Guia pra colocar o sistema rodando num computador que nunca teve o Vertex ERP
instalado. **Não precisa instalar Python nem Postgres** — está tudo dentro
da própria pasta.

## 0. Qual instalação usar?

- **Loja com 1 PC só**: instale só o **Servidor** (pasta `Servidor/`) — funciona
  exatamente como sempre funcionou, sem nenhuma configuração extra.
- **Loja com mais de um caixa**: um PC (o de sempre, ou um dedicado) recebe o
  **Servidor**, e cada caixa adicional recebe um **Terminal** — mais leve,
  não precisa de banco de dados nem backend próprios, só se conecta ao
  Servidor pela rede local.

## 1. Pré-requisitos

- **Windows 10/11** (64 bits)
- Pra usar Terminal: o PC do Servidor e os PCs dos Terminais precisam estar
  na **mesma rede local** (mesmo Wi-Fi/roteador da loja).

Só isso. Nada mais precisa estar instalado na máquina.

---

## Parte A — Instalação do Servidor

## A.1. Copiar os arquivos

Copie a pasta `Servidor/` inteira pra uma pasta **sem acentos, "ç" ou espaços
incomuns no caminho** — por exemplo `C:\VertexERP-Instalador`. Evite colocar
a pasta direto na Área de Trabalho: no Windows em português, esse caminho
tem acento (`C:\Users\NOME\...\Área de Trabalho\...`) e o banco de dados
portátil não consegue iniciar nesse caso. Se quiser um acesso rápido, crie
um **atalho** apontando pro `VertexERP.exe` e deixe só o atalho na Área de
Trabalho — a pasta de instalação em si que precisa ficar num caminho
simples.

Arquivos da pasta:

```
VertexERP.exe                      <- é nele que você dá dois cliques
VertexERP-Backend/
    VertexERP-Backend.exe
VertexERP-Frontend/
    VertexERP-Frontend.exe
postgres-portable/
icone.ico
```

## A.2. Rodar pela primeira vez

Dois cliques em **`VertexERP.exe`**.

Antes de mais nada, uma pergunta aparece: **"Este PC vai funcionar como
Servidor pros outros caixas da loja?"**

- Responda **Sim** se a loja vai ter mais de um caixa (mesmo que os outros
  ainda não estejam instalados).
- Responda **Não** se esse vai ser o único PC da loja — nesse caso, nada
  muda em relação a uma instalação de PC único de sempre.

Na primeira vez, o sistema demora um pouco mais (10-30 segundos, podendo
levar mais em PCs mais fracos) porque ele:

1. Cria o banco de dados do zero (só acontece uma vez).
2. Sobe o próprio banco de dados junto (não precisa de nada instalado).
3. Cria as tabelas.

Depois disso, a tela **"Comece Grátis"** aparece — é ali que você (o dono
da loja) cria a sua própria conta (nome, e-mail e senha à sua escolha) e dá
um nome pra loja. Não existe usuário/senha pré-definido: a primeira pessoa
a se cadastrar vira automaticamente a administradora do sistema.

Da segunda vez em diante, abre bem mais rápido e já mostra a tela de login
normal, com os dados que ficaram salvos.

### Abriu bem mais devagar que isso (ou parece travado)?

Isso costuma ser o Windows Defender escaneando pela nuvem os `.exe` recém
copiados pra esse PC, que ainda não têm nenhuma reputação conhecida — sem
erro nenhum aparecer, só demora mesmo (às vezes minutos, em vez de segundos).
Da próxima abertura em diante costuma normalizar sozinho, mas dá pra evitar
isso desde a primeira vez: antes de abrir o `VertexERP.exe`, clique com o
botão direito em `excluir_do_defender.ps1` (está do lado dele, dentro dessa
mesma pasta) → **Executar com o PowerShell** → aceite a tela do Windows
pedindo permissão de Administrador. Isso diz pro Defender não escanear essa
pasta a cada abertura. Rode de novo só se reinstalar/mover a pasta do Vertex
ERP pra outro lugar depois.

## A.3. Se respondeu "Sim" (vai ter Terminais): fixar o endereço deste PC

Os Terminais vão se conectar a este PC por um endereço de rede (algo como
`192.168.0.10`) — se esse endereço mudar sozinho depois (comum quando o
roteador distribui IP automaticamente), os Terminais perdem a conexão.
Duas formas de evitar isso, escolha uma:

- **Reserva de IP no roteador** (recomendado): entre nas configurações do
  seu roteador e reserve um IP fixo pro PC do Servidor, usando o endereço
  MAC dele.
- **IP fixo no próprio Windows**: configuração manual de rede — se não tiver
  familiaridade, prefira a opção do roteador.

Pra descobrir o endereço atual do PC, abra o Prompt de Comando e digite
`ipconfig` — o número ao lado de "Endereço IPv4" é o que os Terminais vão
usar.

## A.4. Firewall do Windows

Na primeira vez que o Servidor aceita uma conexão de outro PC, o Windows
normalmente pergunta se deve liberar o acesso ("O Firewall do Windows
bloqueou alguns recursos deste aplicativo") — clique em **Permitir acesso**.

Se esse aviso passar despercebido ou for negado por engano, e os Terminais
não conseguirem conectar, libere manualmente: abra o Prompt de Comando
**como Administrador** no PC do Servidor e rode:

```
netsh advfirewall firewall add rule name="VertexERP" dir=in action=allow protocol=TCP localport=58734
```

---

## Parte B — Instalação de Terminal (caixa adicional)

Só é necessária se a loja tem mais de um caixa. Repita esses passos em cada
PC adicional.

## B.1. Copiar os arquivos

Copie a pasta `Terminal/` inteira (bem mais leve que o Servidor — não tem
banco de dados nem backend dentro) pra uma pasta local nesse PC. Mesma regra
de sempre: caminho sem acentos nem espaços incomuns.

Arquivos da pasta:

```
VertexERP-Frontend/
    VertexERP-Frontend.exe         <- é nele que você dá dois cliques
icone.ico
```

Se quiser, crie um atalho pro `VertexERP-Frontend.exe` na Área de Trabalho.

## B.2. Rodar pela primeira vez

Dois cliques em **`VertexERP-Frontend.exe`**. Como esse PC não tem backend
próprio, a tela **"Conectar ao Servidor"** aparece automaticamente — digite
o endereço do PC-Servidor (o que você anotou no passo A.3, por exemplo
`192.168.0.10`) e clique em **Testar Conexão** pra confirmar que está
alcançando o Servidor antes de salvar.

Depois de salvar, a tela de login normal aparece — use a mesma conta
cadastrada no Servidor (todos os Terminais compartilham os mesmos usuários,
clientes, produtos e vendas).

Da segunda vez em diante, o endereço já fica salvo e não precisa configurar
de novo — só se o PC-Servidor mudar de endereço, aí é só abrir de novo a
tela de "Configurar servidor" (link discreto embaixo da tela de login).

Se a primeira abertura demorar bem mais que o normal, veja a dica de
`excluir_do_defender.ps1` na seção A.2 acima — vale pro Terminal também
(a cópia dele já vem junto na pasta `Terminal/`).

---

## Onde ficam os dados

Tudo fica dentro da pasta `pgdata/` (criada ao lado do `VertexERP.exe`, só
no PC-Servidor, na primeira vez que abrir). Terminais não guardam nada
localmente — se um Terminal for formatado ou trocado, é só reinstalar e
reconectar ao mesmo Servidor. Se quiser fazer backup manual, é só copiar a
pasta inteira do Servidor (com o `pgdata/` junto) pra outro lugar — mas com
o app **fechado** nesse momento, pra não copiar o banco no meio de uma
escrita.

## Backup automático

Já vem ligado por padrão no PC-Servidor, sem precisar configurar nada. Um
backup completo do banco é salvo em `Documentos\VertexERP\Backups\`
(dentro dos Documentos do Windows do usuário que abriu o sistema)
enquanto o Vertex ERP estiver aberto — o primeiro roda logo na abertura,
os seguintes a cada 4 horas. Os backups dos últimos 7 dias ficam todos;
entre 7 e 30 dias fica só o último de cada dia; com mais de 30 dias são
apagados, pra não acumular espaço em disco sem limite.

Terminais não guardam nada localmente, então esse backup só existe (e só
faz sentido) no PC-Servidor.

Se o backup falhar, parar de rodar por mais de 24h ou estiver guardado
só no próprio PC (sem a cópia fora da loja, abaixo), quem é
administrador vê uma **faixa amarela** no topo do sistema e o detalhe em
**Configurações → Backup**.

### Backup fora da loja (recomendado)

O backup automático acima só existe **dentro do mesmo computador** da loja
-- se o PC quebrar, for roubado ou pegar fogo, o backup vai junto. Pra ter
uma cópia fora da loja, configure o Vertex pra salvar uma segunda cópia
dentro de uma pasta sincronizada com OneDrive, Google Drive, Dropbox ou
qualquer serviço parecido (o Vertex não fala com a nuvem diretamente --
só escreve na pasta local, e o programa de sincronização instalado no
Windows leva pra nuvem sozinho, do jeito que ele já faz com qualquer
outro arquivo).

1. Instale e configure o app do OneDrive/Google Drive/Dropbox no
   PC-Servidor, se ainda não tiver.
2. Anote o caminho da pasta sincronizada localmente (ex.:
   `C:\Users\SeuNome\OneDrive\VertexERP-Backups`).
3. Abra o arquivo `.env` (na pasta do Servidor, do lado do
   `VertexERP.exe`) num editor de texto e acrescente uma linha:
   ```
   VERTEXERP_BACKUP_EXTRA=C:\Users\SeuNome\OneDrive\VertexERP-Backups
   ```
4. Salve e reabra o Vertex ERP.

Da próxima vez que o backup automático rodar, uma cópia extra vai pra essa
pasta também (mesma regra de retenção acima) -- o backup local continua
existindo do mesmo jeito de sempre, essa é só uma cópia a mais.

### Restaurar um backup

Use quando o banco estragar, alguém apagar dados por engano, ou o
PC-Servidor for trocado.

1. **Feche o Vertex ERP** no PC-Servidor. No modo Servidor, abra o
   Gerenciador de Tarefas e finalize também o `VertexERP.exe`.
2. **PC novo** (o antigo quebrou): instale o Vertex ERP, abra **uma vez**,
   feche, e copie o `.sql` mais recente da pasta da nuvem (OneDrive etc.)
   pra `Documentos\VertexERP\Backups\` deste PC.
3. Clique com o botão direito em `restaurar_backup.ps1` (na pasta do
   Vertex ERP, do lado do `VertexERP.exe`) → **Executar com o PowerShell**.
4. Escolha o backup na lista (o **1** é o mais recente) e digite `SIM`.
5. Abra o Vertex ERP e confira as últimas vendas.

O banco que estava em uso **não é apagado**: fica guardado como
`vertexerp_antes_restauro_<data>`. Se a restauração falhar no meio, o
script volta tudo como estava. Backup cortado no meio (incompleto) é
recusado antes de começar.

**Teste isso uma vez por mês** (num PC de teste, ou num dia de loja
fechada): backup que nunca foi restaurado é backup que ninguém sabe se
funciona.

### Proteger o banco (instalações antigas)

Instalações feitas antes desta versão usam uma senha de banco igual pra
todas as lojas e deixam qualquer programa do PC-Servidor entrar no banco
sem senha. Instalações novas já nascem protegidas. Pra proteger uma
antiga, **uma vez só**:

1. Feche o Vertex ERP (no modo Servidor, finalize também o
   `VertexERP.exe` no Gerenciador de Tarefas).
2. Clique com o botão direito em `proteger_banco.ps1` → **Executar com o
   PowerShell** → digite `SIM`.

O script guarda uma cópia do `.env` e da configuração do banco antes de
mudar, testa a senha nova no fim e, se algo não funcionar, volta tudo
como estava. A senha nova fica no `.env` (não precisa anotar). Rodar de
novo num banco já protegido não faz nada.

## Acesso remoto (ver a loja de fora)

Por padrão, o app (desktop ou celular) só consegue se conectar ao Servidor
estando na mesma rede da loja (mesmo Wi-Fi). Pra acessar de casa, ou de
qualquer lugar com internet, use uma **VPN privada** — recomendamos o
[Tailscale](https://tailscale.com) (gratuito pra uso pessoal/loja pequena,
até 100 aparelhos). Ele cria uma rede privada só entre os seus aparelhos,
sem expor o Servidor direto na internet pública (bem mais seguro que abrir
porta no roteador).

**Passo a passo:**

1. **Pré-requisito**: o PC-Servidor precisa ter respondido **Sim** na
   pergunta "Este PC vai funcionar como Servidor pros outros caixas da
   loja?" (ver A.2) — mesmo que a loja tenha só 1 PC. Se respondeu Não
   na instalação, abra o arquivo `.env` (na pasta do Servidor) num editor
   de texto, troque a linha `VERTEXERP_HOST=127.0.0.1` por
   `VERTEXERP_HOST=0.0.0.0`, salve e reabra o Vertex ERP.
2. Instale o Tailscale no PC-Servidor ([tailscale.com/download](https://tailscale.com/download))
   e entre com uma conta (Google, Microsoft etc.) — a mesma conta vai ser
   usada em todos os aparelhos que devem ter acesso.
3. Instale o Tailscale no celular (ou notebook) que vai acessar de fora,
   entrando com a **mesma conta**.
4. No PC-Servidor, abra o Tailscale e anote o endereço mostrado ali (algo
   como `100.x.y.z`, ou um nome tipo `nome-do-pc.suaconta.ts.net`).
5. No app (fora da rede da loja), use esse endereço em "Configurar
   servidor" (desktop) ou na tela de conectar (celular) — exatamente do
   mesmo jeito que usaria o IP local da rede da loja.

Detalhe de segurança: como esse endereço não é da rede local da loja, se o
certificado do Servidor mudar (por exemplo, depois de reinstalar o
Servidor) o app vai pedir confirmação explícita antes de confiar de novo,
em vez de confiar sozinho — é esperado, funciona como um alerta de
segurança extra pra conexões de fora.

## Independência entre lojas diferentes

Cada Servidor é uma loja independente — o login criado num Servidor não
existe em nenhum outro. Se você administra mais de uma loja, cada uma
precisa do seu próprio Servidor (os Terminais de uma loja só conseguem
falar com o Servidor daquela mesma loja).
