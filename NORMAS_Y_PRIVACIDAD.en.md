# NOVA AI · Terms of use and Privacy policy

Version 1.3 · November 2026

## In a nutshell

- **Your data stays on your PC.** Everything NOVA AI stores (settings, memory, conversation, logbooks, commands and keys) lives on your computer, in the folder `%LOCALAPPDATA%\NOVA AI\datos`. NOVA AI has no servers of its own, doesn't ask for accounts or email, doesn't collect usage statistics or telemetry, and doesn't sell or share your data with anyone.
- **No recordings are made.** The microphone is only used while you talk to Nova. Your voice is not saved to any file: voice training only notes how her name is written when you say it and the measured volume.
- **Internet queries are ordinary queries**, the same ones you could make yourself on Google, the game wiki or any artificial intelligence assistant. They don't carry your files, your email, your passwords or your Star Citizen account data.
- **You're in charge:** you can delete everything whenever you like from Settings › Start over, or when uninstalling.

## What leaves your PC and why

To work, Nova uses free internet services. This is exactly what is sent to each one:

- **Artificial intelligence (Google Gemini, Groq, OpenRouter, DeepSeek):** the text of what you ask Nova and the last messages of the conversation, together with the context she needs to answer well: your name and how you want to be addressed, what you've asked her to remember, your character and a short summary of the game session (location, ship, contracts, party and latest game notices). It's the same as typing it yourself on that AI's website. Only the service in your engine chain is used. Each has its own terms; for example, Google states that on the free Gemini plan it may use what is sent to improve its products.
- **Speech recognition:** if you use Groq to understand your voice, the audio of each sentence is sent to Groq to turn it into text, and it isn't saved on your PC. With local recognition (Whisper) your voice never leaves your computer.
- **Nova's voice:** with the Microsoft Edge voices, the text of the answer is sent to Microsoft to generate the audio. With Piper or the Windows voice nothing is sent.
- **Game information:** searches on Star Citizen Wiki, UEX Corp, scmdb.net and DuckDuckGo about ships, missions, prices or places. At startup, Nova checks whether those sources have new data.
- **Spanish translation:** only if you accept it (and only when NOVA AI is in Spanish), Nova downloads the community translation (0zzyt0) from its Google Drive and installs it in your game folder.
- **Player cards and server status:** when you ask her to look up a player, Nova reads their public profile on robertsspaceindustries.com (only the nickname you type, or that of the target of a bounty on a player that you accept) and that of their organisation; at startup she reads the public page status.robertsspaceindustries.com. They are the same pages you would open in your browser.
- **Planet, moon and place cards:** when you ask about a planet or arrive near one, Nova reads its public page on verseguide.com (for example verseguide.com/location/STANTON/2B) and keeps it for a few days on your computer. Profile pictures and organisation logos are downloaded from robertsspaceindustries.com. If you enable translation, the description (in English) is sent to Google Translate to translate it into your language (or to your AI engine if Google doesn't respond or if you choose the AI in Nova › Token saving). Translations are kept on your computer and not sent again.
- **StarMap:** for data on planets, stations and places (gravity, temperature, services…), Nova queries the public API of starmap.space, asking only for the planet needed, and keeps it for a week on your computer. Other community pages (spviewer.eu, finder.cstone.space, schaulers.com) only open in your browser when you ask.
- **Updates:** at startup and on exit, NOVA asks GitHub (api.github.com) which is the latest published version of NOVA AI. If you update, it downloads the official installer from GitHub. This can be turned off in Settings.
- **Discord (optional):** only if you paste the webhook of one of your channels, Nova sends that channel the public card of the player you looked up (and that of bounty targets who are players, if you leave it enabled). Without a webhook nothing is sent.
- **Lookup dictionary:** it's a text file in your data folder. When something isn't in it, Nova looks it up on the public wiki starcitizen.tools (as you would) and translates it with Google Translate; what she learns stays on your PC.
- **NOVA AI language (Spanish, English, Catalan, French or German):** if you choose a language other than Spanish, Nova's fixed phrases, system messages and the manual are translated with Google Translate (translate.googleapis.com) and kept on your PC so they aren't sent again. With «Add your Language global.ini» Nova copies the file you choose into your game folder (keeping a copy of whatever was there) and adjusts user.cfg; that file isn't sent anywhere.
- **Game chat messages:** when you ask her to «send message to chat», the text of that message is sent to Google Translate (translate.googleapis.com) to translate it, just as if you pasted it yourself into translate.google.com. Nova types it into the Star Citizen chat by pressing keys on your PC.

Nothing else leaves your PC. The game's Game.log is read on your computer and the file is never sent: the AI only receives the short game summary from the point above.

## Terms of use

- **Fan project.** NOVA AI is not affiliated with Cloud Imperium Games or Roberts Space Industries. Star Citizen and its trademarks belong to their owners.
- **Play fair.** Nova presses keys for you, like VoiceAttack or other voice assistants. Use her with common sense: one order, one action. Don't use her to automate the game while you're away, or for anything against Star Citizen's terms of use. You are responsible for complying with them.
- **Free keys included (if your version has them).** Some versions of the program come with free trial keys for Gemini, Groq, OpenRouter and DeepSeek. They have a shared daily limit, may run out or stop working at any time, and must not be copied to other programs. You can enter your own free keys in Nova › Intelligence. By using them you also accept each provider's terms.
- **The AI can be wrong.** Answers are generated by an artificial intelligence and may contain errors. When she makes something up, Nova confesses it at the end with humour. Don't make important decisions based only on what she says.
- **Third-party content.** The translation is the work of the community (0zzyt0). scmdb.net data is licensed CC BY-NC-ND 4.0: it is downloaded to your PC for your personal use and must not be redistributed.
- **No warranty.** NOVA AI is offered free and as is, without warranties of any kind. Its authors are not liable for losses or damage arising from its use, including in-game penalties.

## Your rights and how to exercise them

- **See your data:** Settings › Files › Data folder opens the folder where everything is.
- **Delete it:** Settings › Start over deletes what Nova has learned about you. When uninstalling, tick «Also delete my data» to leave nothing behind.
- **Changes to these terms:** if they change, the installer will ask you to accept them again before installing the new version.

By pressing «Accept» you confirm that you have read and accept these Terms of use and this Privacy policy.
