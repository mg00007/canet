# AURELIA Voz para Windows

Aplicativo desktop para Windows 10/11 x64. No modo ao vivo, ele escuta continuamente, detecta pausas curtas, transcreve cada frase em português localmente com Whisper Base, consulta a OpenAI e sintetiza a resposta com a voz escolhida. O glossário editável ajuda a reconhecer nomes próprios. O modelo é preparado ao abrir o programa; a primeira execução pode baixar cerca de 145 MB.

O seletor inclui somente `pt-BR-FranciscaNeural` e `pt-BR-ThalitaMultilingualNeural`. O idioma de reconhecimento fica fixado em português; vozes de outros locales não aparecem no seletor. O campo permite falar texto digitado ou enviá-lo como pergunta à IA. O corretor offline ajusta palavras desconhecidas e alguns erros comuns de acentuação antes do envio.

## Configurar a IA

1. Crie uma chave de API na [plataforma OpenAI](https://platform.openai.com/api-keys) e habilite faturamento na conta.
2. Cole a chave no campo mascarado do programa. Ela fica apenas na memória durante a sessão; também é possível abrir o app com a variável `OPENAI_API_KEY` configurada.
3. Fale no modo ao vivo ou digite uma pergunta e clique em **Perguntar à IA e falar a resposta**. O app usa `gpt-4o-mini` e mantém até cinco trocas recentes apenas na memória.

O texto transcrito/digitado é enviado à OpenAI para gerar a resposta, e o texto da resposta é enviado ao Microsoft Edge TTS para sintetizar a voz. O áudio do microfone não é enviado à API da OpenAI. O uso da API pode gerar cobrança conforme a conta e o volume de mensagens.

Cada frase começa a ser sintetizada após uma pausa de 0,30 s. Em testes com voz neural limpa, uma frase curta levou 1,82 s para transcrever e 0,85 s para sintetizar; uma fala de 12 s levou de 2,42 a 4,23 s para transcrever. Esses valores variam com o PC e a conexão, e ruído ou pronúncia podem causar erros. O corretor é local e palavra a palavra: ajuda com typos e casos comuns como `voce` → `você`, mas não entende o contexto (por exemplo, `esta`/`está`) e pode exigir revisão. O vocabulário editável protege nomes próprios. A transcrição roda no computador. Somente o texto reconhecido é enviado ao Microsoft Edge TTS; o áudio original do microfone não é enviado ao serviço de voz.

## Gerar o executável

1. Instale Python 3.11 x64 no Windows.
2. Execute `build_windows.bat`.
3. O executável será criado em `dist\AURELIA_Voice\AURELIA_Voice.exe`; o pacote portátil ficará em `AURELIA_Voice_Windows.zip`.

O primeiro build precisa de internet para instalar os pacotes. Na primeira execução, o Whisper baixa o modelo de reconhecimento; a síntese também precisa de internet.

## Usar como microfone em chamadas

1. Clique em **Obter VB-CABLE** ou baixe do site oficial da [VB-Audio](https://vb-audio.com/Cable/), instale como administrador e reinicie o Windows.
2. Clique em **Atualizar dispositivos**; o programa deve mostrar `Pronto: CABLE Input → CABLE Output`.
3. Abra o AURELIA Voz; selecione seu microfone físico e `CABLE Input` como saída.
4. No Discord, Meet ou outro aplicativo, selecione `CABLE Output` como microfone.
5. Clique em **Iniciar conversão ao vivo**. As frases reconhecidas geram respostas da IA e são enviadas ao microfone virtual pela voz selecionada. Clique novamente para parar.

O dispositivo de áudio virtual é criado pelo driver oficial VB-CABLE durante a instalação, com permissão de administrador; o app não instala nem distribui drivers do Windows. Sem o VB-CABLE, a voz pode ser ouvida nos alto-falantes, mas não aparecerá como microfone em outros aplicativos.

## Download pelo GitHub Actions

O workflow `.github/workflows/build-windows-voice.yml` gera o pacote para Windows. Depois de enviar estes arquivos ao GitHub, execute **Build AURELIA Voice for Windows** em Actions e baixe o artefato `AURELIA-Voice-Windows`.