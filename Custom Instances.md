How to setup and run a custom instance.

The docker stack runs:

- Postgres
- Redis

Each instance gets:

- A postgres database
- A redis database
- A bot container
- A web container (includes saq)

Base docker

```yaml
x-shared-variables: &common-variables
  POSTGRES_HOST: suggestions_custom_db
  POSTGRES_USER: suggestions_custom_db_user
  POSTGRES_PASSWORD: password
  POSTGRES_PORT: 2403
  INFISICAL_ID: XXX
  INFISICAL_SECRET: XXX
  INFISICAL_PROJECT_ID: XXX
  INFISICAL_SLUG: prod
  SITE_NAME: Suggestions
  REQUIRE_MFA: 1
  HAS_IMPLEMENTED_OAUTH: 1
  USE_CF_TURNSTILE: 1
  TRUSTED_PROXIES: 1
  CHECK_PASSWORD_AGAINST_HIBP: 1
  DONT_SEND_EMAILS: 1
  IS_CUSTOM_BOT: "1"
  ENABLE_FREE_GUILD_PREMIUM: "1"
  ENABLE_FREE_USER_PREMIUM: "1"
  ENABLE_CUSTOM_NAME_AND_AVATARS: "1"


services:
  suggestions_custom_redis:
    image: redis:8.4.0-alpine
    container_name: "suggestions_custom_redis"
    restart: unless-stopped
    ports:
      - '127.0.0.1:2402:2402'
    command: redis-server --port 2402 --save 20 1 --loglevel warning --requirepass password
    volumes:
      - cache:/data
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 256M
  suggestions_custom_db:
    image: postgres:17
    container_name: "suggestions_custom_db"
    command: -p 2403
    restart: unless-stopped
    ports:
      - "127.0.0.1:2403:2403"
    environment:
      PGDATA: /var/lib/postgresql/data/pgdata
      POSTGRES_DB: suggestions_custom_db
      POSTGRES_USER: suggestions_custom_db_user
      POSTGRES_PASSWORD: password
    volumes:
      - .db:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '5'
          memory: 6G
        reservations:
          cpus: '1'
          memory: 1G

volumes:
  cache:
    driver: local

networks:
  default:
    external: true
    name: spook
```

Then each custom instance gets the following where XXX is the identifier

```yaml
suggestions_XXX_saq:
  image: ghcr.io/suggestionsbot/v4_suggestions_saq:master
  container_name: "suggestions_XXX_saq"
  restart: unless-stopped
  depends_on:
    - suggestions_custom_redis
    - suggestions_XXX_web
  environment:
    <<: *common-variables
    CLUSTER_NAME: XXX
    POSTGRES_DB: XXX
    REDIS_URL: "redis://default:password@suggestions_custom_redis:2402/X"
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 275M
  suggestions_XXX_web:
    container_name: "suggestions_XXX_web"
    image: ghcr.io/suggestionsbot/v4_suggestions_web:master
    restart: unless-stopped
    ports:
      - "127.0.0.1:2500:2500"
    depends_on:
      - suggestions_custom_db
      - suggestions_custom_redis
    environment:
      <<: *common-variables
      SERVING_DOMAIN: "XXX-dashboard.suggestions.gg"
      PORT: 2500
      POSTGRES_DB: XXX
      REDIS_URL: "redis://default:password@suggestions_custom_redis:2402/X"
      CLUSTER_NAME: XXX
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 275M
  suggestions_XXX_bot:
    container_name: "suggestions_XXX_bot"
    image: ghcr.io/suggestionsbot/v4_suggestions_bot:master
    restart: unless-stopped
    depends_on:
      - suggestions_custom_db
      - suggestions_custom_redis
    environment:
      <<: *common-variables
      CLUSTER_NAME: XXX
      TOTAL_SHARDS: "1"
      SHARDS_PER_CLUSTER: "10"
      SYNC_APPLICATION_COMMANDS: "1"
      POSTGRES_DB: XXX
      REDIS_URL: "redis://default:password@suggestions_custom_redis:2402/X"
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 325M
```

From within portainer, navigate to the postgres db and also create the table:

```shell
psql -U suggestions_custom_db_user -d suggestions_custom_db -p 2403 -c 'CREATE DATABASE XXX;'
psql -U suggestions_custom_db_user -d suggestions_custom_db -p 2403 -c '\l'
```

Text for users:

```text
If you are keen you will need to create your own bot which can be done using the following guide: https://discordjs.guide/legacy/preparations/app-setup

When you have completed that, share the token with me via this link: https://secrets.skelmis.co.nz/secret-request/secret/XXX
```

Also need to make instructions for OAuth callback if they want the dashboard exposed. The URL redirect is
`https://XXX-dashboard.suggestions.gg/auth/oauth/discord/authorize`

A side note for the dashboard: Ethan has admin on all deployed instances of the bot when authenticating with OAuth