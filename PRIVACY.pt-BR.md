# Política de Privacidade

[English](PRIVACY.md) · **Português (BR)**

## Resumo

O Transcritor de Áudio de Zap roda inteiramente no seu computador. Não tem servidor por trás.
O autor não opera servidor nenhum, não coleta nada e não recebe nada do seu uso do app — sem
telemetria, sem analytics, sem relatório de erro, sem verificação de atualização, sem conta,
sem cadastro.

O app **envia** o seu áudio para uma API de reconhecimento de fala, porque é exatamente para
isso que ele existe. O serviço é escolha sua e a chave é sua. Esse é o único tráfego de rede
que ele gera.

## O que sai do seu computador

Apenas requisições para o endpoint configurado nas Configurações. O padrão é
`https://api.openai.com/v1`.

| Quando | Requisição | O que é enviado |
|---|---|---|
| Você transcreve um arquivo | `POST /audio/transcriptions` | O conteúdo do arquivo de áudio e o nome dele, o modelo escolhido e o código do idioma, se você fixou um em vez de `auto` |
| A limpeza GPT ou o Reescrever roda | `POST /chat/completions` | O **texto** transcrito e o prompt. O áudio não é enviado de novo |
| Você clica em "Testar chave" | `GET /models` | Nada além da própria chave |

Sua chave de API viaja no cabeçalho `Authorization` dessas requisições. Nada mais é
transmitido — nenhum identificador de máquina, nenhum contador de uso, nenhuma lista de
arquivos.

Se você apontar o campo **Endpoint** para outro serviço compatível com a API v1 da OpenAI
(LM Studio, Ollama, Groq, Azure OpenAI, seu próprio servidor), essas mesmas requisições vão
para lá. O app avisa quando o endpoint usa `http://` puro fora do localhost, porque nesse caso
a sua chave viajaria em texto claro.

## O que fica no seu computador

| Item | Onde | Observação |
|---|---|---|
| Preferências | `%APPDATA%\TranscricaoApp\config.json` | Modelos, idioma do áudio, tema, idioma da interface, prompt personalizado, endpoint. **Nunca a chave de API** |
| Chave de API | Gerenciador de Credenciais do Windows, alvo `TranscritorDeAudio/OpenAI` | Cifrada por DPAPI sob a sua conta do Windows — só abre no seu usuário, nesta máquina |
| Seus arquivos de áudio | Onde você os deixou | O app lê no lugar. Nunca copia, nunca move e não envia para outro destino além do endpoint acima |
| Arquivos temporários | `%TEMP%` | Criados só para converter Opus para tocar, ou para compactar arquivo acima de 25 MB. Apagados quando o app fecha normalmente |
| Transcrições | Só na memória | Existem na janela até você fechá-la, e vão para o disco apenas quando você clica em "Salvar .txt" |

O log de atividade que aparece na janela do app fica em memória e nunca é gravado em arquivo.

Se um `config.json` antigo, de versão anterior, ainda tiver uma `api_key` em texto plano, o app
remove essa chave do arquivo ao carregar e a migra para o Gerenciador de Credenciais.

A limpeza dos temporários roda quando o app fecha normalmente. Se ele for encerrado à força ou
quebrar, um arquivo temporário pode sobrar em `%TEMP%` até o Windows limpar.

## O terceiro que você escolheu

Quando o seu áudio chega à OpenAI — ou a qualquer endpoint que você tenha configurado — o que
acontece com ele passa a ser regido pelos termos daquele serviço, não por este app. O autor não
tem visibilidade nenhuma sobre isso e não tem acordo algum com eles em seu nome.

No caso da OpenAI, veja as [políticas de uso de dados da API](https://openai.com/policies/api-data-usage-policies)
e a [Política de Privacidade](https://openai.com/policies/privacy-policy) deles.

Se você prefere que nenhum áudio saia da sua rede, aponte o campo Endpoint para um servidor
local, como LM Studio ou Ollama.

## O que o autor recebe

Nada.

A única outra atividade de rede que o app pode provocar é abrir um link no seu navegador quando
você clica em um — as páginas de cadastro, de chaves de API e de cobrança da OpenAI, ou a
página do projeto no GitHub.

## Alterações

Este documento descreve o app na versão publicada atualmente. Alterações saem com uma versão e
ficam registradas no [CHANGELOG.md](CHANGELOG.md).

## Dúvidas

Abra uma issue em [github.com/ffapd1989/voice-note-transcriber](https://github.com/ffapd1989/voice-note-transcriber/issues).
