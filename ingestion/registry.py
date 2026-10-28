from . import commons, darul_kutub, internet_archive, isxaki, kazanutlary, kfu, kfu_vakyt, magarif, miras, tatarica, tatargalyame, tatkniga


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga, "miras": miras, "commons": commons,
           "isxaki": isxaki, "internet_archive": internet_archive,
           "kfu_books": kfu.CollectionAdapter("27574"),
           "kfu_manuscripts": kfu.CollectionAdapter("18503"),
           "kfu_il": kfu.CollectionAdapter("28060", tatar_only=True),
           "kfu_azad_halyk": kfu.CollectionAdapter("27528", tatar_only=True),
           "kfu_vakyt": kfu_vakyt,
           "kfu_shura": kfu.CollectionAdapter("25046", tatar_only=True),
           "tatargalyame": tatargalyame}

# Keep the original diagnostic command available after promoting its adapter.
PILOT_SOURCES = {"miras": miras.ARCHIVE_URL}
