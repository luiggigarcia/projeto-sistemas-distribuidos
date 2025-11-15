# Projeto — Sistemas Distribuídos
Aluno: Luiggi Paschoalini Garcia

Este repositório contém um projeto acadêmico de sistemas distribuídos implementado em Python (com pequenos clientes em Node.js e Java). O objetivo é demonstrar padrões de comunicação (REQ/REP e PUB/SUB), sincronização de relógios (algoritmo de Berkeley combinado com um relógio lógico) e um serviço de referência para descoberta e eleição entre servidores.

Sumário de ferramentas utilizadas:
- Linguagens: Python (serviços), Java (cliente), JavaScript (client-bot)
- Bibliotecas principais: ZeroMQ (pyzmq), MessagePack (msgpack)
- Padrões de comunicação:
  - REQ/REP — operações síncronas do cliente e endpoints administrativos do servidor (login, listar usuários, publicar, enviar mensagem direta, etc.).
  - PUB/SUB — entrega assíncrona de mensagens entre usuários/canais e anúncios do sistema.

Estrutura do repositório
- `req-rep/` — servidor REQ/REP (`servidor.py`), servidor de referência (`reference.py`) e `admin_tool.py` (ferramenta de administração).
- `pub-sub/` — serviço de publicação e inscrição de tópicos.
- `js-bot/` — bot Node.js que gera tráfego de teste.
- `Docker/` — Dockerfiles e `docker-compose.yml` para orquestração local.
- `req-rep/storage-server/` — arquivos persistidos localmente (logins, canais, históricos).

- `req-rep/reference.py` — serviço de referência: fornece `rank`, `list`, `heartbeat`, `clock` e `election`.
- `req-rep/servidor.py` — servidor REQ/REP com serviços de aplicação (login, users, channel(s), publish, message), relógio lógico e relógio de aplicação para sincronização (Berkeley). Possui endpoint administrativo (porta `5600 + rank`).
- `req-rep/admin_tool.py` — CLI de administração para testes (list, poll-clock, election, set-clock, announce).

---

## Como rodar (passo-a-passo)

Pré-requisitos
- Docker e Docker Compose instalados.
- (Opcional) Git para clonar o repositório.

1) Clonar o repositório:

```bash
git clone https://github.com/luiggigarcia/projeto-sistemas-distribuidos
cd projeto-sistemas-distribuidos
```

2) Iniciar serviços com Docker Compose

O compose está em `Docker/docker-compose.yml`. Exemplo para levantar 3 réplicas do servidor e 2 bots:

```bash
cd Docker
docker compose up --build --scale servidor=3 --scale clientbot=2
```

Observação: use `--scale` repetido para cada serviço que quiser escalar (como no exemplo acima).

3) Verificar containers e logs

```bash
docker ps
docker compose -f Docker/docker-compose.yml ps
docker compose -f Docker/docker-compose.yml logs -f reference
```

4) Ferramenta administrativa (fora dos containers)

```bash
docker exec -it <nome do servidor> sh
python3 admin_tool.py list
```

- Forçar eleição (enviar `election` para todos os servidores):

```bash
python3 admin_tool.py election --all
```

- Ver clocks dos servidores:

```bash
python3 admin_tool.py poll-clock
```

- Anunciar coordenador manualmente:

```bash
python3 admin_tool.py announce --coordinator servidor1
```

---

## Operações dos servidores — como testar

Você pode testar as operações:
- Usando o cliente Java (`Cliente.java`) para executar operações de usuário reais (login, publish, message, etc.).

Principais serviços REQ/REP:
- `login`
  - Dados: `{ "service":"login", "data": { "user":"nome", "timestamp":"HH:MM:SS", "clock": N } }`
  - Comportamento: registra o usuário em `/app/storage-server/logins.txt` se não existir; responde `status: "sucesso"` ou `status: "logado"`.
  - Teste: no `Cliente.java` escolha opção 1 (Login).

- `users`
  - Retorna a lista de usuários (lê `logins.txt`). Teste: Cliente opção 2.

- `channel` / `channels`
  - `channel` cria um canal (grava `channels.txt`), `channels` lista canais. Teste: opções 3/4 no Cliente.

- `publish`
  - Publica mensagem em um canal via PUB/SUB (proxy), grava `historico_pubsub.txt`.
  - Teste: Cliente opção 5 ou `pub-sub/publisher.py` para publicar direto no proxy.

- `message`
  - Mensagem direta: verifica destino, publica no tópico do usuário destino e grava `historico_msg.txt`.
  - Teste: Cliente opção 6.

Como acompanhar resultados nos servidores:
- `docker compose logs -f <service>` ou `docker logs -f <container>`; servidores usam `pretty_print` para logs legíveis.

O cliente mantém um relógio lógico e atualiza ao receber respostas com campo `clock`.


## Relógios — como está implementado

O projeto usa dois tipos de relógio:

1) Relógio lógico
  - Variável `logical_clock` no servidor e `clock` no cliente Java.
  - Incrementa antes de enviar mensagens (`increment_clock_before_send()`); ao receber mensagem com campo `clock` atualiza se o recebido for maior (`update_clock_on_receive()`).
  - Serve para ordenação causal simples de eventos.

2) Relógio de aplicação + algoritmo de Berkeley
  - Cada servidor mantém `app_time` (Unix epoch float).
  - O coordenador (eleito) executa `perform_berkeley_sync()` periodicamente (controlador dispara após cada 10 mensagens) para pedir tempos, calcular média e instruir ajuste (`clock` admin message com `time: avg`).
  - A eleição escolhe o servidor com maior `rank`.

---

## Eleição de coordenador (detalhes)

- Fluxo: servidores registram-se no `reference` (obtêm `rank`). Se um servidor detecta ausência do coordenador ou acha necessário, chama `perform_election()`.
- `perform_election()` pede a lista ao `reference`, escolhe o servidor com maior `rank`, define `coordinator_name` e publica anúncio no tópico `servers`.
- Todos os servidores subscritos ao tópico `servers` atualizam seu `coordinator_name` quando recebem a mensagem.

---

## Comandos úteis / exemplos rápidos

- Listar servidores:
```bash
python3 req-rep/admin_tool.py list
```

- Forçar eleição:
```bash
python3 req-rep/admin_tool.py election --all
```

- Ver clocks de todos os servidores:
```bash
python3 req-rep/admin_tool.py poll-clock
```

- Anunciar coordenador no tópico `servers`:
```bash
python3 req-rep/admin_tool.py announce --coordinator servidor2
```
