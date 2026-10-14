# AURELIA Voz para Windows

Aplicativo desktop para Windows 10/11 x64. Ele grava trechos de até 25 segundos, transcreve em português localmente com Whisper e sintetiza o texto com a voz neural `pt-BR-FranciscaNeural` usada no comercial.

Isto não é conversão timbre-a-timbre em tempo real: a fala é transcrita e sintetizada depois que a gravação para. A transcrição roda no computador. O texto editado é enviado pela internet ao Microsoft Edge TTS para gerar o áudio; o áudio gravado não é enviado ao serviço de voz.

## Gerar o executável

1. Instale Python 3.11 x64 no Windows.
2. Execute `build_windows.bat`.
3. O executável será criado em `dist\AURELIA_Voice\AURELIA_Voice.exe`; o pacote portátil ficará em `AURELIA_Voice_Windows.zip`.

O primeiro build precisa de internet para instalar os pacotes. Na primeira transcrição, o Whisper baixa o modelo de reconhecimento; a primeira síntese também precisa de internet.

## Usar como microfone em chamadas

1. Instale o [VB-CABLE](https://vb-audio.com/Cable/) e reinicie o Windows.
2. Abra o AURELIA Voz; selecione seu microfone e `CABLE Input` como saída.
3. No Discord, Meet ou outro aplicativo, selecione `CABLE Output` como microfone.
4. Clique em **Iniciar gravação**, fale, pare, revise a transcrição e clique em **Gerar voz e enviar à saída**.

Sem o VB-CABLE, o áudio pode ser ouvido pelos alto-falantes, mas não aparecerá como microfone em outros aplicativos. O driver virtual deve ser baixado e instalado separadamente do site oficial da VB-Audio.

## Download pelo GitHub Actions

O workflow `.github/workflows/build-windows-voice.yml` gera o pacote para Windows. Depois de enviar estes arquivos ao GitHub, execute **Build AURELIA Voice for Windows** em Actions e baixe o artefato `AURELIA-Voice-Windows`.