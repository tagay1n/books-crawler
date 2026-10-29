"""Exact source-label classification shared by adapters and file reviews."""


TATAR_LABELS = {"tt", "tat", "tatar", "татарский", "татарча", "татар теле"}
OTHER_LANGUAGE_LABELS = {"ru", "rus", "russian", "русский", "ar", "ara", "arabic", "арабский",
                         "fa", "fas", "per", "persian", "персидский", "ba", "bak", "bashkir", "башкирский",
                         "crh", "crimean tatar", "крымскотатарский", "tr", "tur", "turkish", "турецкий",
                         "en", "eng", "english", "английский", "de", "deu", "ger", "german", "немецкий"}


def language_selection(values):
    """Classify supplied labels; unknown labels require review, not inference."""
    labels = {" ".join(value.casefold().split()) for value in values if isinstance(value, str) and value.strip()}
    if labels & TATAR_LABELS:
        return "selected"
    return "excluded" if labels and labels <= OTHER_LANGUAGE_LABELS else "review"
