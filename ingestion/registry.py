from . import commons, darul_kutub, internet_archive, isxaki, kazanutlary, magarif, miras, tatarica, tatkniga


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga, "miras": miras, "commons": commons,
           "isxaki": isxaki, "internet_archive": internet_archive}

# Keep the original diagnostic command available after promoting its adapter.
PILOT_SOURCES = {"miras": miras.ARCHIVE_URL}
