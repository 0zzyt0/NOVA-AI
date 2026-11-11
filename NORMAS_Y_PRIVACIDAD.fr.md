# NOVA AI · Conditions d'utilisation et Politique de confidentialité

Version 1.3 · novembre 2026

## En bref

- **Vos données restent sur votre PC.** Tout ce que NOVA AI enregistre (réglages, mémoire, conversation, journaux de bord, commandes et clés) se trouve sur votre ordinateur, dans le dossier `%LOCALAPPDATA%\NOVA AI\datos`. NOVA AI n'a pas de serveurs propres, ne vous demande ni compte ni e-mail, ne collecte ni statistiques d'utilisation ni télémétrie, et ne vend ni ne partage vos données avec qui que ce soit.
- **Aucun enregistrement n'est fait.** Le microphone n'est utilisé que pendant que vous parlez à Nova. Votre voix n'est enregistrée dans aucun fichier : l'entraînement vocal note seulement comment son nom s'écrit quand vous le prononcez et le volume mesuré.
- **Les requêtes sur internet sont des requêtes ordinaires**, les mêmes que vous pourriez faire vous-même sur Google, sur le wiki du jeu ou avec n'importe quel assistant d'intelligence artificielle. Elles ne contiennent ni vos fichiers, ni votre e-mail, ni vos mots de passe, ni les données de votre compte Star Citizen.
- **C'est vous qui décidez :** vous pouvez tout effacer quand vous voulez depuis Réglages › Repartir de zéro, ou lors de la désinstallation.

## Ce qui sort de votre PC et pourquoi

Pour fonctionner, Nova utilise des services internet gratuits. Voici exactement ce qui est envoyé à chacun :

- **Intelligence artificielle (Google Gemini, Groq, OpenRouter, DeepSeek) :** le texte de ce que vous demandez à Nova et les derniers messages de la conversation, avec le contexte dont elle a besoin pour bien répondre : votre nom et la façon dont vous voulez qu'elle s'adresse à vous, ce que vous lui avez demandé de retenir, votre personnage et un court résumé de la partie (position, vaisseau, contrats, groupe et dernières alertes du jeu). C'est la même chose que de l'écrire vous-même sur le site de cette IA. Seul le service présent dans votre chaîne de moteurs est utilisé. Chacun a ses propres conditions ; par exemple, Google indique que, dans l'offre gratuite de Gemini, il peut utiliser ce qui est envoyé pour améliorer ses produits.
- **Reconnaissance vocale :** si vous utilisez Groq pour comprendre votre voix, l'audio de chaque phrase est envoyé à Groq pour être converti en texte, et il n'est pas conservé sur votre PC. Avec la reconnaissance locale (Whisper), votre voix ne quitte jamais votre ordinateur.
- **Voix de Nova :** avec les voix de Microsoft Edge, le texte de la réponse est envoyé à Microsoft pour générer l'audio. Avec Piper ou la voix de Windows, rien n'est envoyé.
- **Informations du jeu :** recherches sur Star Citizen Wiki, UEX Corp, scmdb.net et DuckDuckGo sur les vaisseaux, missions, prix ou lieux. Au démarrage, Nova vérifie si ces sources ont de nouvelles données.
- **Traduction en espagnol :** uniquement si vous l'acceptez (et seulement avec NOVA AI en espagnol), Nova télécharge la traduction de la communauté (0zzyt0) depuis son Google Drive et l'installe dans votre dossier du jeu.
- **Fiches de joueurs et état des serveurs :** quand vous lui demandez de rechercher un joueur, Nova lit sa fiche publique sur robertsspaceindustries.com (uniquement le pseudo que vous saisissez, ou celui de la cible d'une prime sur un joueur que vous acceptez) et celle de son organisation ; au démarrage, elle lit la page publique status.robertsspaceindustries.com. Ce sont les mêmes pages que vous ouvririez dans votre navigateur.
- **Fiches de planètes, lunes et lieux :** quand vous lui demandez des informations sur une planète ou que vous arrivez près d'une planète, Nova lit sa page publique sur verseguide.com (par exemple verseguide.com/location/STANTON/2B) et la conserve quelques jours sur votre ordinateur. Les photos de profil et les logos des organisations sont téléchargés depuis robertsspaceindustries.com. Si vous activez la traduction, la description (en anglais) est envoyée à Google Translate pour être traduite dans votre langue (ou à votre moteur d'IA si Google ne répond pas ou si vous choisissez l'IA dans Nova › Économie de tokens). Les traductions sont conservées sur votre ordinateur et ne sont pas renvoyées.
- **StarMap :** pour les données des planètes, stations et lieux (gravité, température, services…), Nova interroge l'API publique de starmap.space, en ne demandant que la planète nécessaire, et la conserve une semaine sur votre ordinateur. Les autres pages de la communauté (spviewer.eu, finder.cstone.space, schaulers.com) ne s'ouvrent dans votre navigateur que lorsque vous le demandez.
- **Mises à jour :** au démarrage et à la fermeture, NOVA demande à GitHub (api.github.com) quelle est la dernière version publiée de NOVA AI. Si vous mettez à jour, elle télécharge l'installateur officiel depuis GitHub. Cela peut être désactivé dans Réglages.
- **Discord (facultatif) :** uniquement si vous collez le webhook de l'un de vos salons, Nova envoie sur ce salon la fiche publique du joueur que vous avez recherché (et celle des cibles de prime qui sont des joueurs, si vous le laissez activé). Sans webhook, rien n'est envoyé.
- **Dictionnaire de consultations :** c'est un fichier texte dans votre dossier de données. Quand quelque chose n'y figure pas, Nova le cherche sur le wiki public starcitizen.tools (comme vous le feriez) et le traduit avec Google Translate ; ce qu'elle apprend reste sur votre PC.
- **Langue de NOVA AI (espagnol, anglais, catalan, français ou allemand) :** si vous choisissez une autre langue que l'espagnol, les phrases fixes de Nova, les messages du système et le manuel sont traduits avec Google Translate (translate.googleapis.com) et conservés sur votre PC pour ne pas être renvoyés. Avec « Ajoutez le global.ini de votre langue », Nova copie dans votre dossier du jeu le fichier que vous choisissez (en gardant une copie de l'existant) et ajuste user.cfg ; ce fichier n'est envoyé nulle part.
- **Messages dans le chat du jeu :** quand vous lui demandez « envoie un message au chat », le texte de ce message est envoyé à Google Translate (translate.googleapis.com) pour être traduit, exactement comme si vous le colliez vous-même dans translate.google.com. Nova le tape dans le chat de Star Citizen en appuyant sur les touches de votre PC.

Rien d'autre ne sort de votre PC. Le Game.log du jeu est lu sur votre ordinateur et le fichier n'est jamais envoyé : l'IA ne reçoit que le court résumé de la partie mentionné plus haut.

## Conditions d'utilisation

- **Projet de fans.** NOVA AI n'est affilié ni à Cloud Imperium Games ni à Roberts Space Industries. Star Citizen et ses marques appartiennent à leurs propriétaires.
- **Jouez fair-play.** Nova appuie sur les touches à votre place, comme VoiceAttack ou d'autres assistants vocaux. Utilisez-la avec bon sens : un ordre, une action. Ne l'utilisez pas pour automatiser le jeu en votre absence, ni pour quoi que ce soit de contraire aux conditions d'utilisation de Star Citizen. Vous êtes responsable de leur respect.
- **Clés gratuites incluses (si votre version en contient).** Certaines versions du programme incluent des clés d'essai gratuites pour Gemini, Groq, OpenRouter et DeepSeek. Elles ont une limite quotidienne partagée, peuvent s'épuiser ou cesser de fonctionner à tout moment, et ne doivent pas être copiées dans d'autres programmes. Vous pouvez saisir vos propres clés gratuites dans Nova › Intelligence. En les utilisant, vous acceptez aussi les conditions de chaque fournisseur.
- **L'IA peut se tromper.** Les réponses sont générées par une intelligence artificielle et peuvent contenir des erreurs. Quand elle invente quelque chose, Nova vous l'avoue à la fin avec humour. Ne prenez pas de décisions importantes uniquement sur la base de ce qu'elle dit.
- **Contenu de tiers.** La traduction est l'œuvre de la communauté (0zzyt0). Les données de scmdb.net sont sous licence CC BY-NC-ND 4.0 : elles sont téléchargées sur votre PC pour votre usage personnel et ne doivent pas être redistribuées.
- **Sans garantie.** NOVA AI est proposé gratuitement et tel quel, sans aucune garantie. Ses auteurs ne sont pas responsables des pertes ou dommages découlant de son utilisation, y compris les sanctions en jeu.

## Vos droits et comment les exercer

- **Voir vos données :** Réglages › Fichiers › Dossier de données ouvre le dossier où tout se trouve.
- **Les effacer :** Réglages › Repartir de zéro efface ce que Nova a appris de vous. Lors de la désinstallation, cochez « Effacer aussi mes données » pour ne rien laisser.
- **Modifications de ces conditions :** si elles changent, l'installateur vous demandera de les accepter à nouveau avant d'installer la nouvelle version.

En appuyant sur « J'accepte », vous confirmez avoir lu et accepté ces Conditions d'utilisation et cette Politique de confidentialité.
