# Der Automat

Postet jeden Tag eine Story und alle paar Tage einen Beitrag auf Instagram — ohne dass
jemand daran denken muss. Läuft kostenlos auf GitHub.

Was er kann:

- **Design-Stories** — Foto, Logo, Headline in Akira, roter Abuget-Schriftzug, Adresse unten
- **Foto-Stories** — nur das Bild, kein Text
- **Beiträge (4:5)** — gleiches Design plus fertiger Beitragstext
- meldet sich selbst per GitHub-Issue, wenn der Themenplan zur Neige geht

Pro Kunde ein Ordner unter `kunden/`. Prime Döner postet Stories **und** Beiträge,
DönerFabriq nur Stories.

---

## Einrichtung — einmal, Schritt für Schritt

### Schritt 1: Repository anlegen

1. Auf github.com oben rechts auf **+** → **New repository**
2. Name: `isik-automat`
3. Wichtig: **Public** auswählen, nicht Private.
   Grund: Instagram muss die fertigen Bilder selbst herunterladen können, und das geht nur
   bei einem öffentlichen Repository.
   **Deshalb kommen hier niemals Zugangsdaten rein.** Tokens gehören ausschließlich in die
   Secrets (Schritt 4). Die sind auch bei einem öffentlichen Repo geheim.
4. **Create repository**
5. Den Inhalt dieses Ordners hochladen (per Drag-and-drop auf der GitHub-Seite oder mit
   `git push`)

### Schritt 2: Instagram vorbereiten

1. Instagram-App → Einstellungen → **Konto** → **Konto­typ** → auf **Professional / Business**
   umstellen (nicht „Creator")
2. Dieses Instagram-Konto mit einer **Facebook-Seite** verknüpfen
   (Instagram → Einstellungen → Verknüpfte Konten → Facebook)
3. Ohne diese beiden Punkte lässt Meta kein automatisches Posten zu — da führt kein Weg dran
   vorbei.

### Schritt 3: Zugangsdaten bei Meta erzeugen

1. [business.facebook.com](https://business.facebook.com) öffnen → **Einstellungen**
   (Zahnrad unten links)
2. Links **Benutzer** → **Systembenutzer** → **Hinzufügen**
   Name z. B. `Automat`, Rolle **Admin**
3. Beim neuen Systembenutzer auf **Assets zuweisen** → die Facebook-Seite auswählen →
   Vollzugriff
4. Auf **Neues Token generieren**
   - App auswählen (falls noch keine da ist: [developers.facebook.com](https://developers.facebook.com)
     → Meine Apps → App erstellen → Typ **Business**)
   - Ablauf: **Niemals**
   - Berechtigungen anhaken: `instagram_basic`, `instagram_content_publish`,
     `pages_show_list`, `pages_read_engagement`
5. Das Token wird **nur einmal angezeigt** — sofort kopieren.
6. Die Instagram-Account-ID holen: im Browser diese Adresse aufrufen und `DEIN_TOKEN` ersetzen:
   ```
   https://graph.facebook.com/v21.0/me/accounts?fields=instagram_business_account{id,username}&access_token=DEIN_TOKEN
   ```
   In der Antwort steht bei `instagram_business_account` eine lange Zahl — das ist die ID.

### Schritt 4: Zugangsdaten im Repository hinterlegen

Im Repository oben auf **Settings** → links **Secrets and variables** → **Actions** →
**New repository secret**. Vier Stück anlegen:

| Name | Inhalt |
|---|---|
| `IG_TOKEN_PRIMEDOENER` | das Token aus Schritt 3 |
| `IG_ACCOUNT_PRIMEDOENER` | die Zahl aus Schritt 3.6 |
| `IG_TOKEN_DOENERFABRIQ` | dasselbe für DönerFabriq |
| `IG_ACCOUNT_DOENERFABRIQ` | dasselbe für DönerFabriq |

Secrets sind nach dem Speichern nicht mehr lesbar — auch nicht für dich. Das ist so gewollt.

### Schritt 5: Erster Lauf

1. Im Repository auf **Actions**
2. Links **Stories posten** → rechts **Run workflow** → grüner Knopf
3. Nach etwa einer Minute den Lauf anklicken. Grüner Haken heißt: Story ist online.
4. Rot? Auf den Lauf klicken, die rote Zeile aufklappen — da steht im Klartext, was fehlt.
   Meistens ein Tippfehler im Secret.

Ab jetzt läuft es von allein: Stories täglich gegen 11:40 Uhr, Beiträge gegen 17:25 Uhr.

---

## Laufender Betrieb

### Fotos nachliefern

Neue Fotos in den Google-Drive-Ordner des Kunden legen. Ich hole sie dort ab, schneide sie
zu, lege sie unter `kunden/<kunde>/fotos/` ab und fülle den Themenplan nach.

Je mehr Material, desto weniger wiederholt sich. Faustregel: **20 bis 30 Fotos pro Monat**
reichen locker.

### Themenplan

`kunden/<kunde>/plan.json` ist die Liste dessen, was gepostet wird. Ein Eintrag sieht so aus:

```json
{
  "datum": "2026-11-05",
  "typ": "story",
  "foto": "duerum_sossen.jpg",
  "headline": ["ALLES DRAUF,", "WAS DU WILLST"],
  "script": "deine Wahl",
  "bias_y": 0.16
}
```

- `typ`: `story` (Design), `foto` (nur Bild) oder `feed` (Beitrag, braucht zusätzlich `caption`)
- `bias_y`: welcher Teil des Fotos im Hochformat zu sehen ist. 0 = oben, 1 = unten
- `erledigt`: schreibt der Automat selbst rein, sobald gepostet wurde

Der Plan bestimmt den Takt. Fällt ein Lauf aus, bleibt der Eintrag offen und wird am
nächsten Tag nachgeholt — es geht nichts verloren.

### Etwas von Hand posten

Actions → **Stories posten** → **Run workflow**. Nimmt den nächsten offenen Eintrag.

### Etwas stoppen

Actions → links den Workflow wählen → oben rechts **···** → **Disable workflow**.

---

## Kosten

0 €. GitHub Actions ist für öffentliche Repositories unbegrenzt kostenlos, die
Instagram-API kostet nichts.

## Wenn etwas klemmt

| Fehler | Ursache |
|---|---|
| `OAuthException`, Code 190 | Token abgelaufen oder falsch → Schritt 3 wiederholen |
| `Media ID is not available` | Konto ist kein Business-Konto oder nicht mit der Facebook-Seite verknüpft → Schritt 2 |
| `Meta konnte das Bild nicht verarbeiten` | Repository ist nicht öffentlich → Schritt 1 |
| Workflow läuft gar nicht | GitHub pausiert Zeitpläne nach 60 Tagen ohne Aktivität. Einmal **Run workflow** drücken reicht. |
