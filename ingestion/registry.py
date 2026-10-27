from . import commons, darul_kutub, internet_archive, isxaki, kazanutlary, kfu, magarif, miras, tatarica, tatargalyame, tatkniga


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga, "miras": miras, "commons": commons,
           "isxaki": isxaki, "internet_archive": internet_archive,
           "kfu_books": kfu.CollectionAdapter("27574"),
           "kfu_manuscripts": kfu.CollectionAdapter("18503"),
           "kfu_il": kfu.CollectionAdapter("28060", tatar_only=True),
           "tatargalyame": tatargalyame}

# Keep the original diagnostic command available after promoting its adapter.
PILOT_SOURCES = {"miras": miras.ARCHIVE_URL}
