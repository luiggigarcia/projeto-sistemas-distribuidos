Este repositório contém um projeto didático de sistemas distribuídos implementado em Python (com pequenos clientes em Node e Java). O foco foi demonstrar padrões de comunicação (REQ/REP e PUB/SUB), sincronização de relógios (Berkeley) e um serviço de referência para descoberta e eleição entre servidores.

Sumário de ferramentas utilizadas:
- Linguagens: Python, Java (cliente), JavaScript (client-bot de teste)
- Bibliotecas principais: ZeroMQ (pyzmq), MessagePack (msgpack) — usamos MessagePack.
- Padrões de comunicação: REQ/REP para operações de login, listar usuários, publicar, enviar mensagem direta, PUB/SUB para entrega de mensagens entre usuários e para anúncios de eleição/coordenador.

Estrutura do repositório
- `req-rep/` — implementação do servidor REQ/REP, referência, e utilitários de administração.
- `pub-sub/` — scripts simples de publisher/subscriber para testar o sistema de tópicos.
- `js-bot/` — bot em Node.js que gera tráfego de teste.
- `Docker/` — Dockerfiles e `docker-compose.yml` para orquestrar os serviços localmente.
- `req-rep/storage-server/` — arquivos de dados persistidos localmente (logins, canais, históricos).

- Servidor de referência (`req-rep/reference.py`): mantém lista de servidores, aloca `rank` determinístico, aceita `heartbeat` e responde `rank`, `list`, `heartbeat`, `clock`, `election`.
- Servidor REQ/REP (`req-rep/servidor.py`): trata operações de `login`, `users`, `channel(s)`, `publish`, `message` (mensagens diretas). Integra relógio lógico (Lamport) e relógio de aplicação para sincronização via algoritmo de Berkeley. Possui um endpoint administrativo (porta `5600 + rank`) para consultas `clock`/`election` entre servidores.
- Eleição simples: eleição determinística baseada em `rank` (maior rank vence) e publicação do coordenador no tópico `servers` via PUB/SUB.
- Bot em Node (`js-bot/`): gera tráfego de teste — entra, publica em canais e envia mensagens.

Como rodar (passo-a-passo)
Pré-requisitos
- Docker e Docker Compose instalados na sua máquina.
- Opcional: Git para clonar o repositório.

1) Clonar o repositório:

```bash
git clone https://github.com/luiggigarcia/projeto-sistemas-distribuidos
cd projeto-sistemas-distribuidos
```

2) Construir e iniciar os serviços usando Docker Compose

Este projeto foi pensado para rodar em containers. O `docker-compose.yml` está em `Docker/docker-compose.yml`.

Para rodar localmente em modo de teste com 3 réplicas do servidor e 2 bots de cliente:

```bash
cd Docker
docker compose -f docker-compose.yml up -d --build servidor=3 --scale clientbot=2
```

3) Verificar se os containers estão rodando

```bash
docker ps
docker logs -f <container-name>    # por exemplo docker logs -f docker-servidor-1
```

4) Verificar servidores registrados na referência

Os servidores anunciam-se para o serviço de referência que persiste em `req-rep/storage-server/servers.txt` (volume montado no container). Você pode inspecionar esse arquivo no host:

```bash
cat req-rep/storage-server/servers.txt
```

5) Testar operações básicas

```bash
# exemplo: listar servidores
python3 req-rep/admin_tool.py list

# exemplo: solicitar eleição entre servidores
python3 req-rep/admin_tool.py election --all
```

Arquivos importantes
- `req-rep/servidor.py` — lógica principal do servidor REQ/REP, relógios e administração entre servidores.
- `req-rep/reference.py` — serviço de referência (rank, list, heartbeat).
- `req-rep/admin_tool.py` — utilitário para enviar requisições administrativas (list, clock, election).
- `pub-sub/publisher.py` e `pub-sub/subscriber.py` — ferramentas manuais para testar tópicos.

## Testando com o cliente Java (passo-a-passo)
```bash
cd Docker
2) Conectar-se ao cliente Java (duas opções):

- Usar `docker attach cliente`
Observações sobre `docker attach`:
- Para se desanexar sem parar o container, pressione `Ctrl-p` seguido de `Ctrl-q`.
- `docker attach` conecta sua entrada/saída ao processo principal do container (neste caso, o menu do cliente Java). Se quiser abrir um novo shell no container em paralelo, use `docker exec -it cliente sh`.

3) O menu do cliente Java

Quando você conectar ao cliente verá um menu com as opções numeradas. Abaixo explico cada opção e o que ela faz, o que esperar no servidor e como acompanhar os resultados:


O utilitário `req-rep/admin_tool.py` facilita operações administrativas e de depuração entre servidores e o serviço de referência. Abaixo explico cada comando e mostro exemplos de uso.
1) `list` — listar servidores registrados
	- O comando pergunta a `reference` pela lista de servidores registrados.
2) `poll-clock` — perguntar o `clock` (admin endpoint) de todos os servidores
	- Envia `service: clock` ao endpoint administrativo de cada servidor (porta `5600 + rank`).
3) `election` — solicitar eleição ou checar coordenador
	- Envia `service: election` a servidores.
4) `set-clock` — instruir um servidor a ajustar seu relógio de aplicação

5) `announce` — publicar coordenador no tópico `servers`
	- Publica uma mensagem no tópico `servers` para que todos os servidores (ou listeners) atualizem seu `coordinator_name`.
	- Uso:



