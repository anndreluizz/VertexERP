# Instalando o Vertex ERP numa máquina nova

Guia pra colocar o sistema rodando num computador que nunca teve o Vertex ERP
instalado. **Não precisa instalar Python nem Postgres** — está tudo dentro
da própria pasta.

## 1. Pré-requisitos

- **Windows 10/11** (64 bits)

Só isso. Nada mais precisa estar instalado na máquina.

## 2. Copiar os arquivos

Copie esta pasta inteira pra uma pasta **sem acentos, "ç" ou espaços
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
postgres-portable/
icone.ico
```

## 3. Rodar pela primeira vez

Dois cliques em **`VertexERP.exe`**.

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

## 4. Onde ficam os dados

Tudo fica dentro da pasta `pgdata/` (criada ao lado do `.exe` na primeira
vez que abrir). Se quiser fazer backup manual, é só copiar a pasta inteira
do Vertex ERP (com o `pgdata/` junto) pra outro lugar — mas com o app
**fechado** nesse momento, pra não copiar o banco no meio de uma escrita.

## 5. Backup automático

Isso é configurado à parte, por máquina — se quiser o backup automático
rodando nessa máquina nova também, é só pedir.

## 6. Um PC por loja

Cada instalação é independente — o login criado numa máquina não
existe em nenhuma outra. Se a loja usa mais de um computador, cada um
precisa da sua própria instalação e cadastro (não há sincronização entre
eles hoje).
