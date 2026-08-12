# Instalando o Vertex ERP numa máquina nova

Guia pra colocar o sistema rodando num computador que nunca teve o Vertex ERP
instalado. **Não precisa instalar Python nem Postgres** — está tudo dentro
da própria pasta.

## 1. Pré-requisitos

- **Windows 10/11** (64 bits)

Só isso. Nada mais precisa estar instalado na máquina.

## 2. Copiar os arquivos

Copie esta pasta inteira pra máquina nova (pendrive, nuvem, o que for mais
fácil):

```
VertexERP.exe             <- é nele que você dá dois cliques
VertexERP-Backend.exe
VertexERP-Frontend.exe
postgres-portable/
icone.ico
```

## 3. Rodar pela primeira vez

Dois cliques em **`VertexERP.exe`**.

Na primeira vez, o sistema demora um pouco mais (10-30 segundos) porque ele:

1. Cria o banco de dados do zero (só acontece uma vez).
2. Sobe o próprio banco de dados junto (não precisa de nada instalado).
3. Cria as tabelas.
4. Cria um usuário administrador automaticamente e escreve o e-mail/senha
   num arquivo **`PRIMEIRO_ACESSO.txt`**, do lado do `.exe`.

Abra esse arquivo, use o e-mail e a senha pra entrar no sistema, e depois
**apague o arquivo** (ainda não existe uma tela pra trocar a senha pelo
sistema — se precisar trocar, me chame).

Da segunda vez em diante, abre bem mais rápido e já entra direto com os
dados que ficaram salvos.

## 4. Onde ficam os dados

Tudo fica dentro da pasta `pgdata/` (criada ao lado do `.exe` na primeira
vez que abrir). Se quiser fazer backup manual, é só copiar a pasta inteira
do Vertex ERP (com o `pgdata/` junto) pra outro lugar — mas com o app
**fechado** nesse momento, pra não copiar o banco no meio de uma escrita.

## 5. Backup automático

Isso é configurado à parte, por máquina — se quiser o backup automático
rodando nessa máquina nova também, é só pedir.
