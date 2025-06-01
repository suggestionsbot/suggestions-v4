import json
from pathlib import Path

from bot.localisation import Localisation

localisation = Localisation(Path(".."))
for k in localisation._file_to_locale.keys():
    with open(k.name, "r") as f:
        data = json.loads(f.read())

    new_data = {}
    for name, v in data.items():
        name_split = name.split("_")
        if len(name_split) == 1:
            # New format
            new_data[name] = v
            continue

        if name_split[1] == "ARG":
            new_data[
                (
                    "commands"
                    f".{name_split[0].lower()}"
                    f".options.{name_split[2].lower()}"
                    f".{name_split[3].lower()}"
                )
            ] = v

        elif name_split[1] in ("NAME", "DESCRIPTION"):
            new_data[f"commands.{name_split[0].lower()}.{name_split[1].lower()}"] = v

        elif "INNER" in name:
            # No nice way to automate this
            new_data[f"values.{name.replace("_INNER", "").lower()}"] = v

        else:
            new_data[name] = v

    with open(k.name, "w") as f:
        f.write(json.dumps(new_data, indent=4))
