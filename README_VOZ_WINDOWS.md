# AURELIA Voz para Windows

Aplicativo desktop para Windows 10/11 x64. No modo ao vivo, ele escuta continuamente, detecta pausas curtas, transcreve cada frase em português localmente com Whisper Base e a sintetiza com a voz escolhida. O glossário editável ajuda a reconhecer nomes próprios. O modelo é preparado ao abrir o programa; a primeira execução pode baixar cerca de 145 MB.

O seletor inclui somente `pt-BR-FranciscaNeural` e `pt-BR-ThalitaMultilingualNeural`. O idioma de reconhecimento fica fixado em português; vozes de outros locales não aparecem no seletor. Você também pode digitar texto no campo e reproduzi-lo com a voz selecionada; antes da síntese, o corretor offline ajusta palavras desconhecidas e alguns erros comuns de acentuação.

Cada frase começa a ser sintetizada após uma pausa de 0,30 s. Em testes com voz neural limpa, uma frase curta levou 1,82 s para transcrever e 0,85 s para sintetizar; uma fala de 12 s levou de 2,42 a 4,23 s para transcrever. Esses valores variam com o PC e a conexão, e ruído ou pronúncia podem causar erros. O corretor é local e palavra a palavra: ajuda com typos e casos comuns como `voce` → `você`, mas não entende o contexto (por exemplo, `esta`/`está`) e pode exigir revisão. O vocabulário editável protege nomes próprios. A transcrição roda no computador. Somente o texto reconhecido é enviado ao Microsoft Edge TTS; o áudio original do microfone não é enviado ao serviço de voz.

## Gerar o executável

1. Instale Python 3.11 x64 no Windows.
2. Execute `build_windows.bat`.
3. O executável será criado em `dist\AURELIA_Voice\AURELIA_Voice.exe`; o pacote portátil ficará em `AURELIA_Voice_Windows.zip`.

O primeiro build precisa de internet para instalar os pacotes. Na primeira execução, o Whisper baixa o modelo de reconhecimento; a síntese também precisa de internet.

## Usar como microfone em chamadas

1. Instale o [VB-CABLE](https://vb-audio.com/Cable/) e reinicie o Windows.
2. Abra o AURELIA Voz; selecione seu microfone e `CABLE Input` como saída.
3. No Discord, Meet ou outro aplicativo, selecione `CABLE Output` como microfone.
4. Clique em **Iniciar conversão ao vivo** e fale normalmente. A cada pausa entre frases, o texto e a voz sintetizada são enviados automaticamente à saída escolhida. Clique novamente para parar.

Sem o VB-CABLE, o áudio pode ser ouvido pelos alto-falantes, mas não aparecerá como microfone em outros aplicativos. O driver virtual deve ser baixado e instalado separadamente do site oficial da VB-Audio.

## Download pelo GitHub Actions

O workflow `.github/workflows/build-windows-voice.yml` gera o pacote para Windows. Depois de enviar estes arquivos ao GitHub, execute **Build AURELIA Voice for Windows** em Actions e baixe o artefato `AURELIA-Voice-Windows`.