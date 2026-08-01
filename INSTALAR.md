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

Isso é configurado à parte, no PC-Servidor — se quiser o backup automático
rodando nessa máquina nova também, é só pedir.

## Independência entre lojas diferentes

Cada Servidor é uma loja independente — o login criado num Servidor não
existe em nenhum outro. Se você administra mais de uma loja, cada uma
precisa do seu próprio Servidor (os Terminais de uma loja só conseguem
falar com o Servidor daquela mesma loja).
