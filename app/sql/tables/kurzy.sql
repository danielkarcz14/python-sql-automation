CREATE TABLE kurzy (
    ID_meny INT PRIMARY KEY IDENTITY(1, 1) NOT NULL,
	kod_meny TEXT NOT NULL,
    aktualni_kurz REAL NOT NULL
);