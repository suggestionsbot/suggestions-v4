import io
import json
from pathlib import Path

from bot.localisation import Localisation

localisation = Localisation(Path("./bot"))


def get_all_file_content() -> str:
    content = io.StringIO()
    counter = 0
    for file_path in Path(".").rglob("*.py"):
        if file_path.is_file():
            counter += 1
            content.write(file_path.read_text())

    print(f"{counter} files read")
    return content.getvalue()


def get_valid_keys(content: str) -> set[str]:
    valid_keys = set()
    for k in localisation._file_to_locale:
        with Path(k).open() as f:
            data = json.loads(f.read())

        for translation_key in data.keys():
            if translation_key in content:
                valid_keys.add(translation_key)

    return valid_keys


def remove_invalid_keys(valid_keys: set[str]) -> None:
    for k in localisation._file_to_locale:
        with Path(k).open() as f:
            data = json.loads(f.read())

        keys_to_remove = set()
        for translation_key in data.keys():
            if translation_key not in valid_keys:
                if translation_key.count(".") > 1:
                    # Should catch most ones we feel like removing but actually need
                    # Things like guild configuration use variables in key lookups
                    continue
                keys_to_remove.add(translation_key)

        for translation_key in keys_to_remove:
            data.pop(translation_key)

        with Path(k).open(mode="w") as f:
            f.write(json.dumps(dict(sorted(data.items())), indent=4))


def main():
    all_content = get_all_file_content()
    keys = get_valid_keys(all_content)
    print(f"{len(keys)} found to be valid")
    remove_invalid_keys(keys)


if __name__ == "__main__":
    main()
