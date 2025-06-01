Command Locales
---

Please see [this](https://github.com/suggestionsbot/suggestions-bot-rewrite/issues/9) issue.

---


Files follow [this](https://hikari-lightbulb.readthedocs.io/en/latest/by-examples/090_localization.html) spec.

## Variables

The following variables *should* be available to all translations:

- `$CHANNEL_ID` - The id for the channel this command was executed in
- `$AUTHOR_ID` - The id for the author who executed this command
- `$GUILD_ID` - The id for the guild this command was executed in

### Extra Values

Certain translations require non-standard values, please refer to the code
or existing `en_GB` translation to see what these values are.

#### Guild Configuration Values

All values within the `bot.tables.GuildConfig` class are available as
`$GUILD_CONFIG_<FIELD>` where the field is the uppercase variable name.

**Note:** *These values will not be available for all translations*