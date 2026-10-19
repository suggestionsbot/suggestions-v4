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
  POSTGRES_HOST: suggestions_db
  POSTGRES_USER: suggestions_db_user
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
  suggestions_redis:
    image: redis:8.4.0-alpine
    container_name: "suggestions_redis"
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
  suggestions_db:
    image: postgres:17
    container_name: "suggestions_db"
    command: -p 2403
    restart: unless-stopped
    ports:
      - "127.0.0.1:2403:2403"
    environment:
      PGDATA: /var/lib/postgresql/data/pgdata
      POSTGRES_DB: suggestions_db
      POSTGRES_USER: suggestions_db_user
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
    - suggestions_redis
    - suggestions_web
  environment:
    <<: *common-variables
    CLUSTER_NAME: XXX
    POSTGRES_DB: XXX
    REDIS_URL: "redis://default:password@suggestions_redis:2202/X"
  suggestions_XXX_web:
    container_name: "suggestions_XXX_web"
    image: ghcr.io/suggestionsbot/v4_suggestions_web:master
    restart: unless-stopped
    ports:
      - "127.0.0.1:2500:2500"
    depends_on:
      - suggestions_db
      - suggestions_redis
    environment:
      <<: *common-variables
      SERVING_DOMAIN: "XXX.suggestions.gg"
      PORT: 2500
      POSTGRES_DB: XXX
      REDIS_URL: "redis://default:password@suggestions_redis:2202/X"
      CLUSTER_NAME: XXX
  suggestions_XXX_bot:
    container_name: "suggestions_XXX_bot"
    image: ghcr.io/suggestionsbot/v4_suggestions_bot:master
    restart: unless-stopped
    depends_on:
      - suggestions_db
      - suggestions_redis
    environment:
      <<: *common-variables
      BOT_TOKEN: XXX
      CLUSTER_NAME: XXX
      TOTAL_SHARDS: "1"
      SHARDS_PER_CLUSTER: "10"
      SYNC_APPLICATION_COMMANDS: "1"
      POSTGRES_DB: XXX
      REDIS_URL: "redis://default:password@suggestions_redis:2202/X"
```