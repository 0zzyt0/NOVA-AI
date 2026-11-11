# NOVA AI · Nutzungsbedingungen und Datenschutzerklärung

Version 1.3 · November 2026

## Kurz gesagt

- **Ihre Daten bleiben auf Ihrem PC.** Alles, was NOVA AI speichert (Einstellungen, Gedächtnis, Gespräch, Logbücher, Befehle und Schlüssel), liegt auf Ihrem Computer im Ordner `%LOCALAPPDATA%\NOVA AI\datos`. NOVA AI hat keine eigenen Server, verlangt weder Konten noch E-Mail, sammelt keine Nutzungsstatistiken oder Telemetrie und verkauft oder teilt Ihre Daten mit niemandem.
- **Es werden keine Aufnahmen gemacht.** Das Mikrofon wird nur benutzt, während Sie mit Nova sprechen. Ihre Stimme wird in keiner Datei gespeichert: Das Stimmtraining notiert nur, wie ihr Name geschrieben wird, wenn Sie ihn sagen, und die gemessene Lautstärke.
- **Internetabfragen sind ganz normale Abfragen**, dieselben, die Sie selbst bei Google, im Wiki des Spiels oder bei einem beliebigen KI-Assistenten stellen könnten. Sie enthalten weder Ihre Dateien noch Ihre E-Mail, Ihre Passwörter oder die Daten Ihres Star-Citizen-Kontos.
- **Sie haben die Kontrolle:** Sie können jederzeit alles unter Einstellungen › Von vorn beginnen oder bei der Deinstallation löschen.

## Was Ihren PC verlässt und wozu

Um zu funktionieren, nutzt Nova kostenlose Internetdienste. Genau das wird an jeden einzelnen gesendet:

- **Künstliche Intelligenz (Google Gemini, Groq, OpenRouter, DeepSeek):** der Text dessen, worum Sie Nova bitten, und die letzten Nachrichten des Gesprächs, zusammen mit dem Kontext, den sie für eine gute Antwort braucht: Ihr Name und wie Sie angesprochen werden möchten, was Sie sie sich merken ließen, Ihr Charakter und eine kurze Zusammenfassung der Spielsitzung (Standort, Schiff, Verträge, Gruppe und letzte Spielmeldungen). Das ist dasselbe, als würden Sie es selbst auf der Website dieser KI eingeben. Es wird nur der Dienst verwendet, der in Ihrer Engine-Kette steht. Jeder hat eigene Bedingungen; Google gibt zum Beispiel an, dass es im kostenlosen Gemini-Tarif die gesendeten Inhalte zur Verbesserung seiner Produkte verwenden kann.
- **Spracherkennung:** Wenn Sie Groq zur Erkennung Ihrer Stimme nutzen, wird das Audio jedes Satzes an Groq gesendet, um es in Text umzuwandeln, und nicht auf Ihrem PC gespeichert. Mit der lokalen Erkennung (Whisper) verlässt Ihre Stimme Ihren Computer nie.
- **Novas Stimme:** Mit den Microsoft-Edge-Stimmen wird der Text der Antwort an Microsoft gesendet, um das Audio zu erzeugen. Mit Piper oder der Windows-Stimme wird nichts gesendet.
- **Spielinformationen:** Suchen in Star Citizen Wiki, UEX Corp, scmdb.net und DuckDuckGo zu Schiffen, Missionen, Preisen oder Orten. Beim Start prüft Nova, ob diese Quellen neue Daten haben.
- **Spanische Übersetzung:** Nur wenn Sie zustimmen (und nur mit NOVA AI auf Spanisch), lädt Nova die Community-Übersetzung (0zzyt0) aus deren Google Drive herunter und installiert sie in Ihrem Spielordner.
- **Spieler-Steckbriefe und Serverstatus:** Wenn Sie sie bitten, einen Spieler zu suchen, liest Nova dessen öffentliches Profil auf robertsspaceindustries.com (nur den Spielernamen, den Sie eingeben, oder den des Ziels eines Kopfgelds auf einen Spieler, das Sie annehmen) und das seiner Organisation; beim Start liest sie die öffentliche Seite status.robertsspaceindustries.com. Es sind dieselben Seiten, die Sie im Browser öffnen würden.
- **Steckbriefe von Planeten, Monden und Orten:** Wenn Sie nach einem Planeten fragen oder in seine Nähe kommen, liest Nova dessen öffentliche Seite auf verseguide.com (zum Beispiel verseguide.com/location/STANTON/2B) und speichert sie einige Tage auf Ihrem Computer. Profilbilder und Organisationslogos werden von robertsspaceindustries.com heruntergeladen. Wenn Sie die Übersetzung aktivieren, wird die (englische) Beschreibung an Google Translate gesendet, um sie in Ihre Sprache zu übersetzen (oder an Ihre KI-Engine, wenn Google nicht antwortet oder wenn Sie die KI unter Nova › Token sparen wählen). Übersetzungen werden auf Ihrem Computer gespeichert und nicht erneut gesendet.
- **StarMap:** Für Daten zu Planeten, Stationen und Orten (Schwerkraft, Temperatur, Dienste…) fragt Nova die öffentliche API von starmap.space ab, nur für den benötigten Planeten, und speichert sie eine Woche auf Ihrem Computer. Andere Community-Seiten (spviewer.eu, finder.cstone.space, schaulers.com) werden nur in Ihrem Browser geöffnet, wenn Sie darum bitten.
- **Updates:** Beim Start und beim Beenden fragt NOVA bei GitHub (api.github.com) nach der neuesten veröffentlichten Version von NOVA AI. Wenn Sie aktualisieren, lädt sie den offiziellen Installer von GitHub herunter. Das lässt sich unter Einstellungen abschalten.
- **Discord (optional):** Nur wenn Sie den Webhook eines Ihrer Kanäle einfügen, sendet Nova an diesen Kanal den öffentlichen Steckbrief des Spielers, den Sie gesucht haben (und den von Kopfgeldzielen, die Spieler sind, falls aktiviert). Ohne Webhook wird nichts gesendet.
- **Abfrage-Wörterbuch:** Es ist eine Textdatei in Ihrem Datenordner. Wenn etwas darin fehlt, sucht Nova es im öffentlichen Wiki starcitizen.tools (wie Sie es tun würden) und übersetzt es mit Google Translate; das Gelernte bleibt auf Ihrem PC.
- **Sprache von NOVA AI (Spanisch, Englisch, Katalanisch, Französisch oder Deutsch):** Wenn Sie eine andere Sprache als Spanisch wählen, werden Novas feste Sätze, die Systemmeldungen und das Handbuch mit Google Translate (translate.googleapis.com) übersetzt und auf Ihrem PC gespeichert, damit sie nicht erneut gesendet werden. Mit „Fügen Sie Ihre Sprach-global.ini hinzu“ kopiert Nova die von Ihnen gewählte Datei in Ihren Spielordner (mit einer Sicherungskopie der vorhandenen) und passt user.cfg an; diese Datei wird nirgendwohin gesendet.
- **Nachrichten im Spiel-Chat:** Wenn Sie sie bitten, „eine Nachricht in den Chat zu senden“, wird der Text dieser Nachricht zur Übersetzung an Google Translate (translate.googleapis.com) gesendet, so als würden Sie ihn selbst in translate.google.com einfügen. Nova tippt ihn in den Star-Citizen-Chat, indem sie Tasten auf Ihrem PC drückt.

Sonst verlässt nichts Ihren PC. Die Game.log des Spiels wird auf Ihrem Computer gelesen und nie gesendet: Die KI erhält nur die oben genannte kurze Zusammenfassung der Spielsitzung.

## Nutzungsbedingungen

- **Fanprojekt.** NOVA AI ist nicht mit Cloud Imperium Games oder Roberts Space Industries verbunden. Star Citizen und seine Marken gehören ihren Inhabern.
- **Spielen Sie fair.** Nova drückt Tasten für Sie, wie VoiceAttack oder andere Sprachassistenten. Nutzen Sie sie mit gesundem Menschenverstand: ein Befehl, eine Aktion. Nutzen Sie sie nicht, um das Spiel in Ihrer Abwesenheit zu automatisieren, oder für irgendetwas, das gegen die Nutzungsbedingungen von Star Citizen verstößt. Sie sind für deren Einhaltung verantwortlich.
- **Kostenlose Schlüssel enthalten (falls Ihre Version welche hat).** Einige Versionen des Programms enthalten kostenlose Testschlüssel für Gemini, Groq, OpenRouter und DeepSeek. Sie haben ein gemeinsames Tageslimit, können jederzeit aufgebraucht sein oder nicht mehr funktionieren und dürfen nicht in andere Programme kopiert werden. Sie können unter Nova › Intelligenz eigene kostenlose Schlüssel eintragen. Mit ihrer Nutzung akzeptieren Sie auch die Bedingungen des jeweiligen Anbieters.
- **Die KI kann sich irren.** Die Antworten werden von einer künstlichen Intelligenz erzeugt und können Fehler enthalten. Wenn sie etwas erfindet, gesteht Nova es am Ende mit Humor. Treffen Sie keine wichtigen Entscheidungen allein aufgrund dessen, was sie sagt.
- **Inhalte Dritter.** Die Übersetzung ist ein Werk der Community (0zzyt0). Die Daten von scmdb.net stehen unter der Lizenz CC BY-NC-ND 4.0: Sie werden für Ihren persönlichen Gebrauch auf Ihren PC heruntergeladen und dürfen nicht weiterverbreitet werden.
- **Keine Gewähr.** NOVA AI wird kostenlos und so, wie es ist, ohne jegliche Gewährleistung angeboten. Die Autoren haften nicht für Verluste oder Schäden aus der Nutzung, einschließlich Sanktionen im Spiel.

## Ihre Rechte und wie Sie sie ausüben

- **Ihre Daten ansehen:** Einstellungen › Dateien › Datenordner öffnet den Ordner, in dem alles liegt.
- **Sie löschen:** Einstellungen › Von vorn beginnen löscht, was Nova über Sie gelernt hat. Markieren Sie bei der Deinstallation „Auch meine Daten löschen“, um nichts zurückzulassen.
- **Änderungen dieser Bedingungen:** Wenn sie sich ändern, bittet Sie der Installer, sie vor der Installation der neuen Version erneut zu akzeptieren.

Mit dem Drücken von „Akzeptieren“ bestätigen Sie, dass Sie diese Nutzungsbedingungen und diese Datenschutzerklärung gelesen haben und akzeptieren.
