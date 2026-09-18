# Política de Segurança

[English](SECURITY.md) · **Português (BR)**

## Como relatar uma vulnerabilidade

Relate **em privado** pelo GitHub: abra um rascunho de advisory em
[Security → Report a vulnerability](https://github.com/ffapd1989/voice-note-transcriber/security/advisories/new).
Assim o relato fica privado até a correção sair.

Por favor, não abra issue pública para problema de segurança.

Inclua, se puder: a versão, o que um atacante ganha com a falha e os passos para reproduzir.

Este é um projeto de hobby com um único mantenedor e sem SLA. Espere uma confirmação em alguns
dias. Se passarem duas semanas sem resposta, considere-se livre para divulgar publicamente.

## Versões com suporte

Apenas a última versão publicada. Não há backport — a correção sai na versão seguinte. As
versões estão listadas no [CHANGELOG.md](CHANGELOG.md).

## Como a sua chave de API é tratada

- Guardada no **Gerenciador de Credenciais do Windows**, sob o alvo
  `TranscritorDeAudio/OpenAI`, cifrada por DPAPI sob a sua conta do Windows. Não é legível por
  outro usuário, nem em outra máquina.
- **Nunca gravada no `config.json`.** Uma chave em texto plano deixada por versão antiga é
  removida do arquivo e migrada para o cofre no primeiro carregamento.
- O botão "Esquecer chave" nas Configurações a apaga do cofre.
- Enviada apenas no cabeçalho `Authorization` das requisições ao endpoint que você configurou.
- O app avisa quando esse endpoint é `http://` puro fora do localhost, já que aí a chave
  viajaria sem criptografia.

**O cofre protege a chave em repouso, não protege de você.** Qualquer processo rodando sob o seu
usuário do Windows consegue ler o seu Gerenciador de Credenciais — é assim que o DPAPI funciona.
Se a sua conta do Windows for comprometida, a chave também foi.

## Integridade do build

- O `ffmpeg.exe` é baixado durante o build a partir dos builds LGPL do BtbN e conferido contra
  um **SHA-256 fixado**. Se o artefato do upstream mudar, o build para em vez de aceitar bytes
  diferentes em silêncio. Veja o [build.ps1](build.ps1).
- A compressão UPX está desativada de propósito — é gatilho clássico de falso-positivo de
  antivírus.
- As dependências estão fixadas em versões exatas no [requirements.txt](requirements.txt).
- O build roda num **ambiente virtual isolado**, então entra no pacote apenas o que o
  `requirements.txt` traz, e nunca uma biblioteca que por acaso esteja instalada em outro
  lugar da máquina de build. As dependências transitivas não estão fixadas, então dois builds
  ainda podem diferir — isto é isolamento, não reprodutibilidade byte a byte.

## Limitação conhecida: as versões não são assinadas

O executável publicado não tem assinatura de código. Na primeira execução o SmartScreen do
Windows avisa sobre "fornecedor desconhecido", e é preciso clicar em
**Mais informações → Executar assim mesmo**.

Certificado de assinatura de código custa dinheiro por ano e, desde junho de 2023, exige token
físico ou HSM na nuvem. Para uma ferramenta gratuita distribuída entre amigos, isso não se
justifica hoje.

**O que isso significa para você:** esse aviso é esperado, e passar por ele não é prova de que o
arquivo é seguro. Se isso importa para você, gere o executável você mesmo a partir do código com
o `build.ps1` e compare com o que você baixou.

## Fora de escopo

- O binário não assinado e o aviso do SmartScreen, descritos acima.
- Qualquer coisa que exija que o atacante já esteja rodando código sob o seu usuário do Windows.
- O comportamento da OpenAI, ou de qualquer outro endpoint que você configure. Veja o
  [PRIVACY.pt-BR.md](PRIVACY.pt-BR.md).
- Falso-positivo de antivírus no pacote do PyInstaller — relate ao fabricante do antivírus.
- O custo das chamadas de API feitas com a sua própria chave.
