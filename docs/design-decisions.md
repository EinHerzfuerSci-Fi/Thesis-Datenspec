# Designentscheidungen der Datenspec

Dieses Dokument erklärt, **warum** die Datenspec so aussieht, wie sie aussieht. Das
**Was** (jedes Feld, jedes Topic) steht im generierten Referenzteil der
[README](../README.md); die Änderungshistorie steht im [CHANGELOG](../CHANGELOG.md).

Stand: Paket 0.5.5, Schema `v = 2`.

> **Quellenlage.** Die Begründungen stammen aus den Docstrings und Kommentaren der
> Modelle, aus README, CHANGELOG und den Commit-Messages. Wo eine Begründung nirgends
> festgehalten ist und nur aus dem Zusammenhang folgt, steht **(abgeleitet)** dabei.
> Dann ist es eine Lesart und sollte bei Gelegenheit bestätigt oder korrigiert werden.

## Inhalt

1. [Kontext und Randbedingungen](#1-kontext-und-randbedingungen)
2. [Architektur: eine Quelle, viele Artefakte](#2-architektur-eine-quelle-viele-artefakte)
3. [Wire-Format](#3-wire-format)
4. [Versionierung und Evolution](#4-versionierung-und-evolution)
5. [Identität, Duplikate und Zeit](#5-identität-duplikate-und-zeit)
6. [Runs](#6-runs)
7. [Profile und Gain-Regelung](#7-profile-und-gain-regelung)
8. [Befehle und Laptop-Nachrichten](#8-befehle-und-laptop-nachrichten)
9. [MQTT-Topics](#9-mqtt-topics)
10. [Messdaten](#10-messdaten)
11. [Health, Konfiguration, Fehler und Logs](#11-health-konfiguration-fehler-und-logs)
12. [Qualitätssicherung](#12-qualitätssicherung)
13. [Bekannte Grenzen und offene Punkte](#13-bekannte-grenzen-und-offene-punkte)

---

## 1. Kontext und Randbedingungen

Die Spec verbindet zwei Welten:

| Seite | Laufzeit | Eigenschaften |
|---|---|---|
| **Messgerät** | Raspberry Pi Pico 2 W, MicroPython | wenig RAM, kein Pydantic, Strom kann jederzeit ausfallen, Uhr erst nach NTP gültig |
| **Auswertung** | CPython ≥ 3.14 auf dem Laptop | volle Validierung, Pydantic, Analyse-Software |

Das Gerät schreibt Records als JSON Lines auf eine SD-Karte **und** publiziert sie per
MQTT. Der Laptop schickt Befehle und Metadaten (Sessions, Notizen, Tags) zurück.

Fast jede Entscheidung unten folgt aus drei Randbedingungen:

1. **Das Gerät ist unzuverlässig verbunden.** WLAN, Broker und SD können ausfallen;
   Nachrichten kommen doppelt, verspätet, lückenhaft oder gar nicht an.
2. **Das Gerät ist knapp an Ressourcen.** Alles, was auf dem Pico laufen muss, muss
   klein sein.
3. **Daten sind Forschungsdaten.** Ein Record muss auch Monate später ohne Kontext
   interpretierbar sein (Einheiten, Konfiguration, Zeitbezug, Herkunft).

---

## 2. Architektur: eine Quelle, viele Artefakte

### D1 · Pydantic-Modelle sind die einzige Quelle der Wahrheit

**Entscheidung.** Die Modelle in `src/datenspec/models/` definieren das Format.
JSON-Schemas, Pico-Konstanten, AsyncAPI-Datei und der Referenzteil der README werden
daraus generiert (`python -m datenspec.codegen`).

**Warum.** Mehrere handgepflegte Beschreibungen desselben Formats laufen auseinander.
Mit einer Quelle kann ein Feld nicht im Schema stehen und in der Doku fehlen.
Pydantic liefert gleichzeitig die Laufzeit-Validierung für die Analyse-Software und
das JSON-Schema für alle anderen Werkzeuge.

**Folgen.**
- Eine Formatänderung ist eine Änderung an einem Modell und danach ein Codegen-Lauf.
- Regeln, die sich in JSON Schema nicht ausdrücken lassen, leben nur im Modell
  (siehe D5).

### D2 · Generierte Dateien sind eingecheckt, und ein Test erzwingt Aktualität

**Entscheidung.** `schemas/`, `pico/datenspec_const.py`, `asyncapi/asyncapi.yaml` und
der Referenzblock der README liegen im Repo. `codegen --check` und
`tests/test_generated.py` schlagen fehl, wenn eine Datei nicht zu den Modellen passt.
Auch verwaiste Schema-Dateien (entfernte Record-Art) fallen auf.

**Warum.** Die Firmware soll `pico/datenspec_const.py` per Submodul oder Kopie
einbinden können, ohne Python-Toolchain. Auch AsyncAPI-Werkzeuge brauchen die Schemas
als Dateien. **(abgeleitet)** Eingecheckt sind sie außerdem als Review-Artefakt: ein
Pull Request zeigt die Formatänderung direkt im Diff der Schemas.

**Folgen.** Eine Modelländerung ohne Regenerieren lässt die Tests rot werden. Die
Generatoren sind deterministisch und byte-genau vergleichbar.

### D3 · Die Pico-Datei enthält nur `NAME = literal`

**Entscheidung.** `datenspec_const.py` besteht ausschließlich aus Zuweisungen von
Literalen: keine Imports, keine Typen, keine Container. Ein Test parst die Datei mit
`ast` und lehnt alles andere ab. Ist `micropython` installiert, importiert ein weiterer
Test die Datei zusätzlich mit dem echten Interpreter, denn dass CPython sie akzeptiert,
beweist nichts für MicroPython.

**Warum.** Jedes Konstrukt darüber hinaus kostet RAM auf dem Pico oder läuft auf
MicroPython nicht. Die Firmware braucht nur die Wire-Strings.

**Folgen.**
- Präfixe machen Werte eindeutig, die in mehreren Rollen vorkommen: `"nir"` ist
  `LED_NIR`, `CH_NIR` und `ILL_NIR`.
- Topics, die nur zwischen Laptop und Pipeline laufen (`session`, `annotation`, `tag`),
  fehlen auf dem Pico, weil sie dort nur RAM kosten würden.
- Feldnamen erscheinen als `F_*` mit der Einheit im Kommentar.

### D4 · JSON Schema 2020-12, und AsyncAPI verweist auf die Schemas

**Entscheidung.** Die Schemas sind Draft 2020-12. Die AsyncAPI-Datei referenziert sie,
statt Payloads zu duplizieren. Topics, QoS und Retain kommen aus
`datenspec.topics`, derselben Quelle wie die Pico-Konstanten.

**Warum.** So bleibt das Schema die einzige Payload-Definition. 2020-12 wird gebraucht,
weil `if`/`then`/`else` und `dependentRequired` für die Querregeln genutzt werden
(Alert, Annotation).

**Folgen.** AsyncAPI-Werkzeuge müssen 2020-12 nicht unterstützen (verpflichtend ist nur
draft-07). Das ist in README und AsyncAPI-Datei so vermerkt, als bewusst
hingenommene Einschränkung.

### D5 · Regeln, die nur das Modell prüft, sind dokumentiert statt versteckt

**Entscheidung.** Einige Invarianten sind Pydantic-Validatoren ohne Entsprechung im
exportierten Schema, etwa: genau eine `dark`-Aufnahme pro Zyklus, `buf.fill ≤ buf.cap`,
`sd.free ≤ sd.total`, `ntp.last_up ≤ up`, Stufenregeln der Gain-Regelung. Die README
führt sie in einem eigenen Abschnitt „Limits of the JSON Schemas“. Wo das Schema die
Regel ausdrücken kann, steht sie in beidem (`alert.ref_seq`, `alert.thr`,
`annotation.run`).

**Warum.** Die Validatoren fangen Fehler, die ein reiner Typcheck nicht sieht. Ein
Schema-only-Konsument soll aber wissen, dass er ein schwächeres Prüfwerkzeug hat, statt
sich in falscher Sicherheit zu wiegen.

**Folgen.** Regeln über **zwei Records** hinweg (Ende nach Start, Captures passen zur
`cfg.capture.sequence`, Gains aus den `stages`) prüft weder Modell noch Schema. Das ist
Aufgabe der Pipeline.

---

## 3. Wire-Format

### D6 · JSON Lines, ein Format für SD und MQTT

**Entscheidung.** Ein Record ist ein JSON-Objekt auf einer Zeile. Dieselbe Zeile wird
auf SD geschrieben und als MQTT-Payload gesendet.

**Warum.** Ein Format bedeutet einen Parser und einen Satz Beispiele. JSON Lines kann
das Gerät anhängend schreiben, ohne die Datei umzuschreiben, und ein abgebrochener
Schreibvorgang beschädigt höchstens die letzte Zeile. **(abgeleitet)**

**Folgen.** SD-Replay und MQTT liefern dieselben Records, deshalb sind Duplikate
erwartet (D20).

### D7 · Ein gemeinsamer Header in jedem Pico-Record

**Entscheidung.** Jeder Pico-Record trägt `v`, `k`, `dev`, `fw`, `boot`, `run`, `seq`,
`up`, `ts`. `k` ist der Diskriminator für die Record-Art.

**Warum.** Jeder Record ist so für sich allein einordenbar: welches Gerät, welche
Firmware, welcher Boot, welcher Run, wie weit seit Start. Das ist nötig, weil SD-Dateien
und MQTT-Ströme ohne Sitzungskontext zusammenfinden müssen.

**Folgen.** `dev` ist die Hardware-ID (`machine.unique_id()`) als 16 Hex-Zeichen. Sie
wird zugleich für Topic-Namen und ACLs genutzt (D44).

### D8 · Kurze Wire-Namen, beschreibende Python-Namen

**Entscheidung.** Dort, wo es die Lesbarkeit hilft, hat das Python-Attribut einen
ausführlichen Namen und der Wire-Name ist ein Alias (`rh` ↔ `relative_humidity`,
`up` ↔ `uptime`, `ts` ↔ `timestamp`). Schemas, Pico-Konstanten und Referenz
verwenden immer den Wire-Namen.

**Warum.** Kurze Namen sparen Bytes pro Record und damit SD-Platz und
Funk-Durchsatz. Der Python-Code soll trotzdem lesbar sein.
**(abgeleitet für die Byte-Ersparnis; die Aufteilung ist im Code dokumentiert.)**

**Folgen.** `SpecModel` akzeptiert Eingabe per Alias **und** per Feldname und
serialisiert per Alias.

### D9 · Einheiten stehen im Schema, nicht im Record

**Entscheidung.** Jedes Feld hat eine feste Einheit, festgehalten als `x-unit` im
Schema. Der Record sendet sie nie mit. Konventionen: °C, Anteile als Bruch 0…1 (nicht
Prozent), V, s, `_ms`/`_hz`/`_nm` im Namen, dBm, Bytes.

**Warum.** **(abgeleitet)** Eine Einheit pro Wert im Record würde jeden Record
aufblähen und wäre trotzdem eine Fehlerquelle, wenn Firmware und Auswertung sie
unterschiedlich interpretieren. Feste Einheiten, die im Schema stehen, sind eindeutig.

**Folgen.** Eine Einheitenänderung ist ein Breaking Change und erhöht `v`
(D15). Relative Feuchte und PWM-Duty sind
dimensionslose Anteile (`x-unit: "1"`); ein Test-Beispiel prüft explizit
„Feuchte in Prozent statt Bruch“.

### D10 · Ausgefallener Sensor = `null`, Schlüssel bleibt Pflicht

**Entscheidung.** Antwortet ein Sensor nicht, steht der Schlüssel mit Wert `null` im
Record. Ein **fehlender** Schlüssel ist ein Fehler. Dasselbe gilt für Gruppen, deren
Subsystem nichts zu berichten hat (`tele.wlan` ohne Verbindung, `tele.ntp` vor dem
ersten Sync, `info.sd` ohne Karte). Gruppen, deren Zustand selbst die Information ist
(`tele.mqtt`, `tele.sd`), sind nie `null`.

**Warum.** **(abgeleitet)** „Sensor ausgefallen“ und „Firmware kennt das Feld nicht“
sind unterschiedliche Aussagen. Wären Schlüssel optional, könnte ein Tippfehler im
Firmware-Code unbemerkt als „fehlender Sensor“ durchgehen.

**Folgen.** Später ergänzte Sensoren sind die Ausnahme: Sie sind optional mit
`default=None`, damit ältere Firmware gültig bleibt (D16).

### D11 · Strikte Typen, keine Koerzion

**Entscheidung.** `SpecModel` läuft mit `strict=True`: `"1.5"` ist keine Zahl, `1.0`
ist keine Ganzzahl.

**Warum.** Die Firmware schreibt die Records selbst. Ein falscher Typ ist ein
Firmware-Fehler, den die Spec sichtbar machen soll, statt ihn stillschweigend zu
korrigieren. **(abgeleitet)**

### D12 · `Literal` statt `Enum`, `str` statt `uuid.UUID`

**Entscheidung.** Geschlossene Wertemengen sind `Literal[...]`. UUIDs sind Strings mit
Regex-Pattern in kanonischer Kleinschreibung.

**Warum.** Im Strict-Modus lehnt Pydantic reine Strings für `Enum`-Felder und
`uuid.UUID`-Felder ab, wenn aus einem Dict validiert wird. Zusätzlich braucht der
Pico-Generator nur die Werte, die `typing.get_args` aus einem `Literal` direkt liefert.

**Folgen.** Eine Wertemenge hat genau einen Ort (`models/vocab.py`) und speist Modelle,
Schemas und Pico-Konstanten.

### D13 · Modelle sind unveränderlich (`frozen=True`)

**Entscheidung.** Alle Spec-Modelle sind frozen.

**Warum.** Records sind Fakten über die Vergangenheit. Unveränderliche Objekte lassen
sich gefahrlos in Mengen und als Dict-Schlüssel führen, und Korrekturen (etwa
`fill_missing_ts`) erzeugen sichtbar eine Kopie mit `model_copy`. **(abgeleitet)**

### D14 · Unbekannte Felder: zur Laufzeit ignorieren, in Tests ablehnen

**Entscheidung.** `parse_record(line)` ignoriert unbekannte Felder.
`parse_record(line, forbid_extra=True)` lehnt sie ab. Das Repo selbst prüft seine
Beispiele nur im zweiten Modus.

**Warum.** Zur Laufzeit soll eine ältere Auswertung Records neuerer Firmware mit
zusätzlichen optionalen Feldern lesen können (Vorwärtskompatibilität). In den Tests
soll dagegen ein Tippfehler in einem Beispiel auffallen, statt als „unbekanntes Feld“
verschluckt zu werden.

**Folgen.** Der Schalter ist ein Validierungs-Kontext (`FORBID_EXTRA`), kein
Modell-Attribut. Beispiele mit `"strict_only": true` dokumentieren genau die Fälle, die
nur im strengen Modus scheitern.

---

## 4. Versionierung und Evolution

### D15 · `v` steigt nur bei Breaking Changes

**Entscheidung.** `v` ist eine ganze Zahl in jedem Record. Sie steigt nur, wenn ein Feld
entfällt oder umbenannt wird, ein Typ oder eine Einheit sich ändert oder ein optionales
Feld Pflicht wird.

**Warum.** Der Leser soll an `v` erkennen können, ob er ein Format versteht. Würde jede
Ergänzung `v` erhöhen, müssten alle Leser ständig mitziehen, obwohl sich für sie nichts
ändert.

### D16 · Additive Änderungen sind optional mit `default=None`

**Entscheidung.** Ein neues optionales Feld, eine neue optionale Gruppe oder ein neuer
Sensor unter `m` ändern `v` nicht. Sie bekommen `default=None`, damit Records älterer
Firmware gültig bleiben. Die Referenz-Spalte „Since v“ (`x-since`) hält fest, wann ein
Feld eingeführt wurde.

**Folgen.** Das ist der bevorzugte Erweiterungsweg. `Measurements`, `InfoRecord` und
`TeleRecord` sind ausdrücklich so aufgebaut, dass neue Subsysteme als optionale Gruppen
hinzukommen.

### D17 · Eine neue Record-Art ist nicht abwärtskompatibel

**Entscheidung.** Ein neuer Wert von `k` gilt als inkompatibel, weil ältere Leser die
ganze Zeile ablehnen. Deshalb ist eine neue optionale Gruppe in einem bestehenden Record
vorzuziehen.

**Warum.** Der `k`-Diskriminator ist eine geschlossene Menge. Ein Leser, der `k` nicht
kennt, kann den Record weder validieren noch sinnvoll ignorieren.

### D18 · v1 wurde nie ausgeliefert und hat keinen Leser

**Entscheidung.** `MIN_SCHEMA_VERSION = SCHEMA_VERSION = 2`. Es gibt keinen v1-Leser,
und `v` ist im Header auf genau `2` begrenzt.

**Warum.** Weder Gerät noch SD-Karte haben jemals v1 geschrieben. Ein Leser für ein nie
produziertes Format wäre toter Code.

**Folgen.** Solange v2 ebenfalls nicht ausgeliefert ist, wird v2 **in place** geändert,
ohne `v` zu erhöhen. Das ist in 0.3.0, 0.4.0 und 0.5.0 geschehen, und der CHANGELOG
benennt jedes Mal, welche Nachrichten der alten Version abgelehnt werden. Sobald echte
Daten existieren, gilt wieder D15 uneingeschränkt.

### D19 · Paketversion und Schemaversion sind getrennt

**Entscheidung.** Das Paket folgt SemVer und wird über Git-Tags veröffentlicht. Die
generierten Dateien tragen beide Versionen im Kopf („datenspec 0.5.5, schema version 2“).

**Warum.** Die Analyse-Software pinnt einen Release-Tag (`pip install ...@v0.3.0`),
unabhängig davon, ob sich das Wire-Format geändert hat. Reine Bugfixes oder neue
Helfer sollen `v` nicht berühren.

---

## 5. Identität, Duplikate und Zeit

### D20 · `seq` zählt pro Record-Art, nicht global

**Entscheidung.** `seq` ist ein Zähler **je Art** (`k`). Für `data` zählt er je Run und
beginnt mit jedem Run bei 0. Für alle anderen Arten zählt er je Boot. Eindeutiger
Schlüssel: `(dev, run, seq)` für `data`, `(dev, boot, k, seq)` sonst.

**Warum.** Ein globaler Zähler würde Lücken falsch deuten, sobald eine Art nur über
MQTT oder nur auf SD gesendet wird: Die übrigen Arten zeigten dann Lücken, die gar
keine Verluste sind. Mit einem Zähler pro Art bedeutet eine Lücke immer „in genau
dieser Art ging etwas verloren“. Für `data` je Run ergibt sich: `seq` läuft von 0 bis `n_data - 1`, und die
Vollständigkeit eines Runs ist direkt prüfbar.

### D21 · Duplikate sind normal; Dedup behält den ersten Record und meldet Konflikte

**Entscheidung.** `datenspec.dedup.deduplicate` behält pro Schlüssel den ersten Record
in Eingabereihenfolge. Unterscheidet sich ein späterer Record mit gleichem Schlüssel im
Inhalt, wird er als `Conflict` gemeldet statt still verworfen.

**Warum.** QoS 1 darf Nachrichten doppelt zustellen, und SD-Replay sendet Records
erneut, die schon per MQTT hinausgingen. Gleicher Schlüssel und gleicher Inhalt ist
ein harmloser Resend. Gleicher Schlüssel und anderer Inhalt kann nur ein Firmware-Fehler
sein (zum Beispiel wiederverwendetes `seq`) und muss sichtbar werden.

### D22 · Jeder Record trägt `up` und `ts`, gemeinsam erfasst

**Entscheidung.** `up` ist monotone Zeit seit Boot in Sekunden mit ms-Auflösung. `ts`
ist Unix-Zeit UTC in Sekunden, `null` bis zum ersten NTP-Sync. Beide werden im selben
Moment erfasst und beziehen sich auf Messung oder Ereignis, nicht auf den Sendezeitpunkt.

**Warum.** Der Pico hat beim Start keine gültige Uhrzeit. Eine Spec, die `ts`
voraussetzt, würde Records vor dem NTP-Sync entweder verwerfen oder mit falscher Zeit
versehen. Mit `up` hat jeder Record eine verlässliche, monotone Zeitachse.

**Folgen.**
- **Intervalle immer aus `up` berechnen**, nicht aus `ts`: `ts` kann bei einem
  NTP-Resync springen, `up` nicht.
- Die Firmware muss `up` gegen den Überlauf von `time.ticks_ms()` (ca. 12,4 Tage)
  schützen und mit `ticks_diff` akkumulieren.
- `ts` ist Pflichtschlüssel mit Wert `null`, nicht optional (D10).

### D23 · Fehlendes `ts` wird nachträglich aus dem Offset desselben Boots rekonstruiert

**Entscheidung.** `datenspec.timestamps.fill_missing_ts` berechnet für synchronisierte
Records den Offset `ts − up` und wendet ihn auf unsynchronisierte Records **desselben
Boots** an. Es nimmt den Offset des nächsten synchronisierten Records (gemessen in `up`),
rundet auf ganze Sekunden und meldet, welche Werte rekonstruiert (`reconstructed`) und
welche nicht auflösbar (`unresolved`) waren.

**Warum.** Der Offset gilt nur innerhalb eines Boots, denn `up` startet bei 0. Er
verschiebt sich außerdem bei einem NTP-Resync. Der nächste Nachbar hält den Fehler
einer solchen Verschiebung lokal. Rekonstruierte Zeiten sind abgeleitet und müssen
von gemessenen unterscheidbar bleiben, deshalb die Rückmeldung.

---

## 6. Runs

### D24 · Der Run ist ein eigenes Konzept, vom Gerät entschieden

**Entscheidung.** Ein Run (Messreihe) wird von der Firmware gestartet und beendet. Sie
sendet einen `run`-Record mit `ev: "start"` vor dem ersten `data`-Record und einen mit
`ev: "end"` nach dem letzten. Beide sind eine Record-Art mit dem Ereignis in `ev`, damit
sie auf demselben Topic laufen.

**Warum.** Messdaten brauchen eine Klammer: Ohne Run ist ein Strom von `data`-Records
eine undifferenzierte Folge. Das Gerät muss entscheiden, weil es auch ohne Laptop
messen können soll (Start am Gerät, Ende durch Dauer oder Fehler).

### D25 · `run` steht im Header jedes Pico-Records, `null` außerhalb

**Entscheidung.** Jeder Pico-Record hat `run`. Außerhalb eines Runs ist er `null`.
`data` existiert nur innerhalb eines Runs und hat deshalb ein Pflicht-`run` ohne `null`.

**Warum.** `tele`, `log`, `err` und `alert` laufen auch ohne Run weiter. Mit `run` im
Header lässt sich jeder Record einem Run zuordnen, ohne Zeitfenster zu raten.

### D26 · Run-IDs kommen aus einem Flash-Zähler, geschrieben vor dem Start-Record

**Entscheidung.** Wie `boot` ist die Run-ID ein Zähler im Flash. Die Firmware
inkrementiert und schreibt ihn, **bevor** sie den Start-Record sendet. `(dev, run)`
identifiziert einen Run.

**Warum.** Bei Stromausfall kann so eine ID übersprungen, aber nie wiederverwendet
werden. Eine wiederverwendete ID würde zwei Runs vermischen. Eine übersprungene ist
harmlos.

### D27 · Ein Boot pro Run, ein unterbrochener Run wird nicht fortgesetzt

**Entscheidung.** Start- und End-Record eines Runs entstehen im selben Boot. Nach einem
Neustart wird ein Run nicht wieder aufgenommen. Folglich sind `seq` des End-Records
größer und `up` größer oder gleich denen des Start-Records.

**Warum.** **(abgeleitet)** Das hält Zeit (`up` startet bei 0) und Zähler (`seq` pro
Boot) innerhalb eines Runs konsistent. Ein Run, der einen Reboot überlebt, bräuchte eine
Zeitbasis-Übersetzung quer über Boots.

**Folgen.** Diese Beziehung zwischen zwei Records kann das Modell nicht prüfen
(D5).

### D28 · `aborted` setzt nur die Pipeline; `n_data` macht Verluste zählbar

**Entscheidung.** Das Gerät sendet nie den Grund „aborted“. `RunEndReason` kennt nur
`duration`, `manual`, `error`. Ein Run ohne End-Record (Stromausfall, Absturz) wird von
der Pipeline als `aborted` markiert. Der End-Record enthält `n_data`, die Zahl der
`data`-Records des Runs.

**Warum.** Ein abgestürztes Gerät kann keinen Abbruch melden. Ein Grund, den nur eine
funktionierende Firmware senden kann, wäre ausgerechnet im Fehlerfall nie vorhanden.
`n_data` zusammen mit `seq = 0 … n_data − 1` macht Verluste innerhalb eines Runs exakt
zählbar.

### D29 · Alarme werden auch außerhalb von Runs überwacht (0.5.0)

**Entscheidung.** `alert.ref_seq` darf `null` sein, und zwar **genau dann**, wenn `run`
`null` ist. Innerhalb eines Runs benennt es weiterhin den `data`-Record, der den
Übergang ausgelöst hat (Schlüssel `(dev, run, ref_seq)`).

**Warum.** Das Gerät überwacht Alarme dauerhaft. Außerhalb eines Runs gibt es keinen
`data`-Record, auf den man verweisen könnte. Die Regel „genau dann“ schließt beide
Fehlerfälle aus: Verweis ohne Run und Run ohne Verweis.

**Folgen.** Die Regel steht als `if/then/else` im Schema **und** als Validator im
Modell. Jeder unter 0.4.0 gültige Alert bleibt gültig.

---

## 7. Profile und Gain-Regelung

### D30 · Profile beschreiben das Wie, der Run das Wann

**Entscheidung.** Ein Profil legt fest, wie ein Run misst (Messintervall,
Capture-Sequenz, Timing, Gain-Regelung). Der Run bestimmt, wann gemessen wird. Das
Gerät hält Profile in einer Datei (Name → `RunConfig`, `ProfileFile`). `cmd start`
nennt ein Profil per Name oder `null` für das Standardprofil.

**Warum.** So kann der Laptop Runs starten, die unterschiedlich messen, ohne dass
Einstellungen im Befehl wandern. `sample_interval_ms` und die `capture`-Gruppe
mussten dafür aus `info` heraus (0.4.0), weil sie nicht mehr pro Boot, sondern pro Run
gelten.

### D31 · Der Start-Record trägt die aufgelösten Einstellungen als Schnappschuss

**Entscheidung.** Der Start-Record enthält den tatsächlich benutzten Profilnamen und
`cfg`, die aufgelösten Einstellungen. Sie gelten für den ganzen Run. Auswerter lesen
sie dort und **nicht** aus der Profildatei.

**Warum.** Die Profildatei kann sich nach dem Run ändern. Ein Run muss ohne sie
interpretierbar bleiben, auch wenn kein Laptop ihn gestartet hat. Es ist dasselbe Prinzip
wie bei den Einheiten (D9):
Interpretierbarkeit darf nicht von externem Zustand abhängen.

**Folgen.** `info.profiles` listet nur `names` und `default`, nicht die Einstellungen,
damit der Laptop einen Namen vor dem Senden prüfen kann, ohne eine zweite, veraltbare
Kopie der Werte zu halten. Ein unbekannter Name wird mit `ack` `rejected` beantwortet.

### D32 · Profilnamen haben ein enges Alphabet

**Entscheidung.** `^[a-z0-9_]+$`, dasselbe Alphabet wie Tag-Schlüssel.

**Warum.** Sicher in Dateinamen, Topics und CLI-Argumenten. Das JSON-Schema der
Profildatei schließt zusätzlich weitere Schlüssel aus (`additionalProperties: false`),
damit ein Editor auch `"Turbidity"` ablehnt. Pydantic exportiert das Key-Pattern allein
nur als `patternProperties`, was andere Schlüssel durchlässt.

### D33 · Eine Capture-Sequenz braucht genau eine `dark`-Aufnahme

**Entscheidung.** `cfg.capture.sequence` enthält genau einmal `dark`. Dieselbe Regel
gilt für `data.m.tcs3448`.

**Warum.** Die Dunkelkorrektur braucht pro Zyklus genau eine Umgebungslicht-Referenz.
Die Regel steht schon im Profil, damit ein Profil, dem der `data`-Record nie genügen
könnte, **dort abgelehnt wird, wo es geschrieben wird**, und nicht erst mitten in einer
Messung.

### D34 · Die Gain-Regelung ist Teil des Profils (0.5.0)

**Entscheidung.** `cfg.capture.gain_control` hat `mode` (`fixed`, `ams`, `dark`) und
`stages` (zulässige Gain-Indizes). `stages` ist genau dann `null`, wenn `mode` `fixed`
ist; sonst mindestens zwei, streng aufsteigende Indizes. `info.tcs3448.agc` sagt, ob der
aktive Run regelt, und ist außerhalb eines Runs `false`.

**Warum.** Runs mit unterschiedlicher Gain-Strategie müssen unterscheidbar und
vergleichbar sein. Die Messwerte hängen vom Gain ab, also gehört die Strategie in die
Run-Konfiguration.

**Folgen.** Jeder `gain` einer Aufnahme eines regelnden Runs muss eine seiner `stages`
sein. Das ist eine Zwei-Record-Regel (D5).
Start-Records aus 0.4.0 ohne die Gruppe werden abgelehnt (Änderung in place, D18).

---

## 8. Befehle und Laptop-Nachrichten

### D35 · Zwei Absender, zwei Header

**Entscheidung.** Pico-Records tragen den vollen Header. Nachrichten des Laptops
(`cmd`, `session`, `annotation`, `tag`) tragen nur `v` und `k`. Sie werden mit
`parse_laptop_message` gelesen, getrennt von `parse_record`.

**Warum.** Der Laptop ist kein Messgerät. `dev`, `boot`, `seq` und `up` hätten dort keine
Bedeutung. Getrennte Parser und Typen machen es unmöglich, versehentlich eine
Laptop-Nachricht als Gerätedaten zu behandeln.

### D36 · Das Ziel eines Befehls steht im Topic, nicht im Payload

**Entscheidung.** `cmd` geht an `thesis/<device_id>/cmd` oder an `thesis/all/cmd`.
Jedes Gerät, das den Befehl erhält, antwortet mit einem eigenen `ack`, das die `id` des
Befehls als `cmd_id` trägt.

**Warum.** **(abgeleitet)** Das Routing übernimmt der Broker, das Gerät braucht keine
Filterlogik im Payload. Bei `all` ist durch das `ack` je Gerät erkennbar, wer reagiert
hat.

### D37 · `stop` nennt den Run, und ein falscher Run wird abgelehnt

**Entscheidung.** `cmd stop` enthält die Run-ID. Ein Gerät ignoriert den Befehl mit
`res: "rejected"`, wenn das nicht sein aktiver Run ist. `cmd start` hat `run: null`,
das Gerät vergibt die ID.

**Warum.** Mit QoS 1 kann ein Stop verspätet oder doppelt ankommen. Ohne Run-ID könnte
ein verspätetes Stop den **nächsten** Run beenden. Die ID macht ihn idempotent.

### D38 · Befehle werden nicht retained

**Entscheidung.** `retain = false` für alle `cmd`-Topics.

**Warum.** Ein retained Befehl würde bei jeder Wiederverbindung des Geräts erneut
ausgeführt.

### D39 · Alle Befehls-Felder sind immer vorhanden

**Entscheidung.** `cmd start` und `cmd stop` haben dieselben Schlüssel (`dur`,
`session`, `profile`, `run`). Nicht anwendbare Felder sind bei `stop` immer `null`. Die
beiden Fälle werden über `act` als diskriminierte Union getrennt.

**Warum.** Gleiche Form erleichtert Firmware-Parser und Beispiele. Der Diskriminator
sorgt dafür, dass Pydantic und das Schema jeweils die passenden Pflichtfelder prüfen,
und nicht anwendbare Werte fest auf `null` setzen, damit sie nicht fälschlich benutzt
werden.

### D40 · Von der CLI erzeugte UUIDs ermöglichen Dedup

**Entscheidung.** `cmd`, `session`, `annotation` und `tag` tragen eine `id` (UUID), die
die CLI erzeugt. Run-Start und Acks verweisen per `cmd_id` und `session` auf sie.

**Warum.** Der Laptop hat keinen `seq`-Zähler (D35).
Die UUID ist sein Identitätsmerkmal, an dem die Pipeline QoS-1-Duplikate erkennt. Sie
verknüpft außerdem Befehl, Ack und Run-Start miteinander.

### D41 · Sessions, Annotationen und Tags laufen nur Laptop → Pipeline

**Entscheidung.** Topics `thesis/laptop/session`, `…/annotation`, `…/tag`. Geräte
publizieren und abonnieren dort nichts, und die Pico-Konstanten lassen sie weg.

**Warum.** Sie gehören zu keinem einzelnen Gerät und heißen deshalb nach dem Absender.
Eine Session bündelt mehrere Runs eines Experiments. Eine Session hat eine `variety`
(`normal`, `calibration`, `functional`, `flowrate`), die für alle ihre Runs gilt.

### D42 · Tags sind eine Ereignishistorie, nicht ein überschreibbarer Zustand

**Entscheidung.** Jede `tag`-Nachricht bleibt als Historie erhalten. Der aktuelle Wert
eines Schlüssels ist der mit dem neuesten `ts`. `value: null` löscht den Tag. Ein Tag
darf vor dem Start-Record seines Runs eintreffen.

**Warum.** Nachrichten kommen nicht in Sendereihenfolge an, und ein Tag kann zu einem
Run gehören, dessen Start-Record noch unterwegs ist. Mit „neuester `ts` gewinnt“ ist der
Endzustand unabhängig von der Ankunftsreihenfolge, und nichts geht verloren.

### D43 · Annotationen: `run` setzt `dev` voraus

**Entscheidung.** Eine Annotation kann sich auf Gerät, Run und Session beziehen. `run`
ohne `dev` ist ungültig. Das Schema bildet das mit `if/then` ab; `dependentRequired`
reicht nicht, weil beide Schlüssel immer vorhanden sind.

**Warum.** Eine Run-ID ist nur zusammen mit dem Gerät eindeutig (`(dev, run)`, D26).

---

## 9. MQTT-Topics

### D44 · Topic-Schema und IDs, das Broker-ACLs ermöglichen

**Entscheidung.** Geräte-Topics folgen `thesis/{device_id}/…`, wobei `device_id` die
Hardware-ID ist, die auch als `dev` im Record steht. `all` und `laptop` können nicht mit
einer ID kollidieren, weil eine ID immer 16 Hex-Zeichen hat.

**Warum.** Weil Topic und `dev` übereinstimmen, kann der Broker einen Client per ACL an
seine eigenen Topics binden. Die Namensräume `all` und `laptop` sind damit
kollisionsfrei reserviert.

### D45 · QoS 1 überall

**Entscheidung.** Alle Topics nutzen QoS 1 (mindestens einmal).

**Warum.** Dokumentiert ist, dass Duplikate durch QoS 1 erwartet und über `seq` bzw.
UUIDs erkennbar sind (D21).
**(abgeleitet)** Daraus folgt die Abwägung: Verlust ist für Forschungsdaten schlimmer
als ein Duplikat, das sich entfernen lässt. Warum nicht QoS 2 gewählt wurde, ist nicht
festgehalten.

### D46 · Retain gezielt: `info`, `status`, `alert`

**Entscheidung.** Retained sind `info`, `status` und `alert`. `data`, `tele`, `run`,
`err`, `log`, `cmd` und `ack` sind es nicht.

**Warum.** Dokumentiert ist die Begründung für `alert` (retained Nachricht = aktueller
Zustand des Alarms) und gegen `cmd` (würde bei jeder Wiederverbindung erneut
ausgeführt). **(abgeleitet)** Für die übrigen gilt dasselbe Prinzip: Retained heißt
„aktueller Zustand für Spätkommer“. Das trifft auf die Boot-Konfiguration (`info`) und
die Erreichbarkeit (`status`) zu. Ereignisse und Messreihen haben keinen solchen
Zustand.

### D47 · Ein Unter-Topic pro Alarm

**Entscheidung.** `thesis/{device_id}/alert/{alarm_id}`, retained.

**Warum.** Retain gilt pro Topic. Mit einem Topic je Alarm ist die retained Nachricht
genau der aktuelle Zustand dieses Alarms (`raised` oder `cleared`). Bei einem gemeinsamen
Topic würde der letzte Alarm die anderen verdrängen. `id` im Payload entspricht der
letzten Topic-Ebene. Gesendet wird nur bei Übergängen, die Hysterese liegt in der Firmware.

### D48 · `status` ist Klartext und zugleich Last Will

**Entscheidung.** `thesis/{device_id}/status` trägt `online` oder `offline` als
`text/plain`, retained. Der Broker veröffentlicht `offline` als Last Will, wenn das
Gerät unerwartet verschwindet.

**Warum.** Die Online-Erkennung muss auch dann funktionieren, wenn das Gerät nichts mehr
senden kann. Dafür ist der Last Will der MQTT-Mechanismus. Weil der Payload ein
einzelnes Wort ist, braucht er kein JSON und kein Modell.

---

## 10. Messdaten

### D49 · Rohwerte sind maßgeblich, abgeleitete Größen optional

**Entscheidung.** `raw` (16-Bit-Zählwerte) ist die Wahrheit. `lux`, `cct`, `cie_x`,
`cie_y` sind optional und werden auf dem Gerät mit der Herstellerbibliothek abgeleitet.
Die kalibrierte Auswertung (Basiszählwerte, Gain-Korrektur, Dunkelabzug, XYZ) gehört
nicht in die Spec, sondern in die Analyse-Software.

**Warum.** Aus Rohwerten lässt sich jede Auswertung später wiederholen oder verbessern.
**(abgeleitet)** Abgeleitete Werte vom Gerät sind Bequemlichkeit, aber an die
Herstellerbibliothek gebunden. Dokumentiert ist, dass die Rohwerte maßgeblich sind und
die kalibrierte Auswertung nicht in dieses Repo gehört.

### D50 · Gesendet werden 13 Spektralkanäle, nicht die SMUX-Slots

**Entscheidung.** `raw` führt die Kanäle `f1…f8`, `fz`, `fy`, `fxl`, `nir`, `vis`. Die
Flicker-Slots (5, 11, 17) werden nicht gesendet. `vis_2` und `vis_3` (VIS aus dem 2. und
3. SMUX-Zyklus) sind optional.

**Warum.** `vis_2`/`vis_3` zeigen Lichtänderungen *während* einer Messung, wenn sie vom
ersten `vis` abweichen (dokumentiert). **(abgeleitet)** Die Slot-Zuordnung ist ein
Detail des Sensors; Auswerter sollen Kanäle sehen, nicht die Multiplexer-Belegung. Warum
die Flicker-Slots ausgelassen werden, ist nicht festgehalten.

### D51 · Pro Zyklus genau eine `dark`-Aufnahme

**Entscheidung.** `data.m.tcs3448` hat genau eine Aufnahme mit `ill: "dark"`, und in ihr
sind alle LED-Duty-Cycles 0.

**Warum.** Das ist die Referenz für den Umgebungslichtabzug. Weniger lässt keine
Dunkelkorrektur zu, mehr wäre mehrdeutig (D33).

### D52 · LEDs: Modell statt Dict, Duty-Cycle ist ein Sollwert

**Entscheidung.** `led` ist ein Modell mit den Pflichtfeldern `nir`, `blue`, `vis`,
kein freies Dict. Der Wert ist ein **Sollwert** (0…1), und die Doku sagt ausdrücklich,
dass die Lichtleistung weder linear zum Duty-Cycle noch unabhängig von der
LED-Temperatur ist.

**Warum.** Mit einem Modell sind alle drei LEDs Pflicht, und ein fehlender Schlüssel
fällt auf. Der Hinweis zur Nichtlinearität verhindert, dass Auswerter den Duty-Cycle als
Lichtmenge lesen.

### D53 · DS18B20: genau ein Sensor, Schlüssel ist die ROM-ID, 85,0 °C wird markiert statt abgelehnt

**Entscheidung.** `m.ds18b20` ist eine Map mit genau einem Schlüssel: der ROM-ID, die
`info.ds18b20.rom` meldet. `info.ds18b20.rom` ist genau dann gesetzt, wenn
`sensors.ds18b20` wahr ist. 85,0 °C ist der Power-on-Wert; die Firmware soll ihn als
`null` senden. Kommt er trotzdem, wird er akzeptiert, und
`Measurements.ds18b20_suspect()` listet die betroffenen ROM-IDs.

**Warum.** Die Map-Form erlaubt es, später mehrere Sensoren abzubilden, ohne das
Format zu brechen **(abgeleitet)**; heute ist es genau einer. Abgelehnt wird 85,0 nicht,
weil damit der **ganze** Record verloren ginge, und 85,0 grundsätzlich auch ein echter
Messwert sein kann.

### D54 · Gain als Index, Vollausschlag wird berechnet statt gesendet

**Entscheidung.** `gain` ist ein Index 0…12 für die Faktoren 0,5; 1; 2; …; 2048. Bei
aktiver Regelung ist es der tatsächlich benutzte Wert, nach der Messung zurückgelesen.
Integrationszeit und Vollausschlag folgen aus `atime` und `astep`:
`(atime+1)·(astep+1)·2,78 µs` bzw. `min(65535, (atime+1)·(astep+1))`.

**Warum.** Vollausschlag steht ausdrücklich als „berechnet, nicht gesendet“ in der
Spec. **(abgeleitet)** Beide Größen sind Funktionen zweier gesendeter Werte; redundante
Felder könnten sich widersprechen.
`datenspec.tcs3448` stellt die Rechnungen als Hilfsfunktionen bereit.

### D55 · Sättigung wird doppelt geprüft

**Entscheidung.** `sat` meldet die Sättigung des Sensors. `tcs3448.capture_flags`
markiert zusätzlich Kanäle bei oder über 90 % des Vollausschlags (`NEAR_FULL_SCALE`,
konfigurierbar).

**Warum.** Kurze Integrationszeiten sättigen unterhalb der 16-Bit-Grenze. Außerdem
soll die Analyse mit Sicherheitsabstand arbeiten können und sich nicht allein auf `sat`
verlassen.

---

## 11. Health, Konfiguration, Fehler und Logs

### D56 · `info` und `tele` sind nach Subsystemen gruppiert

**Entscheidung.** `info` (einmal pro Boot, retained) und `tele` (etwa alle 60 s)
gliedern sich in Gruppen je Subsystem (`sys`, `wlan`, `mqtt`, `sd`, `buf`, `ntp`, …).
Neue Subsysteme kommen als optionale Gruppen hinzu.

**Warum.** Gruppen halten Felder zusammen, die zusammen gehören, und erlauben
Erweiterungen, ohne `v` zu erhöhen (D16).
`info` beschreibt, was während eines Boots fest ist; `sensors` wird ausdrücklich nicht
neu gescannt, daher zeigen `data`-Records, welche Sensoren tatsächlich antworten.

### D57 · `err` und `log` sind getrennte Arten

**Entscheidung.** `err` meldet Modulfehler mit Code (und optional Modulzustand). `log` ist
der allgemeine Diagnosestrom mit Level, Modul, Nachricht und unvalidiertem Kontext.

**Warum.** Fehler sind Ereignisse, die eine Auswertung zählen und filtern will. Logs
sind Freitext für Menschen. Getrennt lassen sie sich unterschiedlich speichern,
filtern und alarmieren. `log.ctx` ist bewusst nicht validiert, weil es
Debug-Information ist, kein Vertrag.

---

## 12. Qualitätssicherung

### D58 · Gültige und ungültige Beispiele pro Record-Art

**Entscheidung.** `examples/valid/<kind>.jsonl` enthält Wire-Records, wie die Firmware
sie auf SD schreibt. `examples/invalid/<kind>.jsonl` enthält je Zeile einen Testfall mit
`case`, `loc` und `record`. Ein ungültiger Fall muss **an der angegebenen Stelle**
(`loc`) scheitern, und jeder gemeldete Fehler muss unterhalb davon liegen.

**Warum.** Ohne `loc` könnte ein Negativtest aus einem unbeabsichtigten Grund bestehen,
etwa einem Tippfehler an anderer Stelle im Record. Mit `loc` testet jeder Fall genau
eine Regel. Die Beispiele dienen zugleich Firmware-Entwicklern als Referenz.

**Folgen.** Jedes gültige Beispiel muss die Pydantic-Modelle **und** die exportierten
JSON-Schemas passieren, sodass Abweichungen zwischen beiden auffallen. Außerdem muss es
beim Serialisieren wieder dieselbe Zeile ergeben (Round-Trip mit Wire-Namen, ohne
geschriebene Defaults). Die ungültigen Fälle laufen gegen die Modelle.

### D59 · Strenge Werkzeuge

**Entscheidung.** Python ≥ 3.14, Pydantic ≥ 2.11 (`validate_by_name` und
`serialize_by_alias` sind ab dieser Version verfügbar), Ruff mit breiter Regelauswahl,
`uv` als Werkzeug. Pydantic-Fehlermeldungen sind der Zweck der Validatoren, daher sind
`TRY003` in Modellen und Generatoren ausgenommen.

---

## 13. Bekannte Grenzen und offene Punkte

- **Schema-only-Konsumenten prüfen weniger.** Ohne die Pydantic-Validatoren sind die in
  D5 genannten Regeln nicht erzwungen.
- **Regeln über mehrere Records** (Ende nach Start, Captures passen zur Sequenz, Gains
  aus den Stufen, Vollständigkeit über `n_data`) liegen bei der Pipeline.
- **AsyncAPI und 2020-12.** Werkzeuge müssen das Format nicht unterstützen.
- **Schema `v2` wurde dreimal in place geändert.** Sobald ein Gerät echte Daten schreibt,
  gilt die Versionsregel D15 ohne Ausnahme; spätere Änderungen an v2 sind dann nicht
  mehr in place möglich.
- **Rekonstruierte `ts`-Werte sind Schätzungen.** Sie sind rundungs- und
  resync-anfällig und müssen in der Auswertung als abgeleitet gekennzeichnet bleiben.
- **Einzelner DS18B20.** Die Spec erzwingt genau einen Sensor pro Gerät. Mehr Sensoren
  würden diese Einschränkung lockern, wären aber ein Formatentscheid.
