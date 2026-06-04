MS Capture — lançador clicável para Windows
==========================================

Descrição
---------

MS Capture é um script em Python para captura e exportação de trechos de partituras do MuseScore 4, aproximando-se da funcionalidade de screenshot/câmera existente no MuseScore 3. O app permite exportar trechos selecionados da partitura em SVG, PNG ou PDF, com opções de controle de resolução e transparência quando aplicável.

Conteúdo desta pasta
--------------------

1. ABRIR_ms_capture.vbs
   - Duplo clique neste arquivo para abrir o app sem PowerShell e sem janela de console.

2. ABRIR_ms_capture_COM_DIAGNOSTICO.bat
   - Use este se o .vbs não abrir nada. Ele mostra mensagens de erro em uma janela de terminal.

3. ms_capture_v4.py
   - Script Python principal.

4. ms_capture_v4.pyw
   - Cópia do script com extensão .pyw. Em algumas instalações do Windows, duplo clique neste arquivo também abre o app diretamente.

Como usar
---------

1. Extraia o ZIP inteiro para uma pasta, por exemplo:
   C:\Users\SEU_USUARIO\Documents\MS_Capture_App

2. Não mova o lançador para fora da pasta sem mover junto o arquivo ms_capture_v4.py.

3. Dê duplo clique em:
   ABRIR_ms_capture.vbs

Requisitos
----------

- Python 3 instalado no Windows.
- Tkinter disponível na instalação do Python.
- MuseScore 4 instalado.

Observação
----------

Isto não é um .exe independente. É um lançador clicável para o script Python. Para criar um .exe autônomo, o caminho recomendado é empacotar o app com PyInstaller no próprio Windows onde MuseScore e Python estão instalados.

Créditos e desenvolvimento
--------------------------

Este script foi desenvolvido no âmbito do grupo de pesquisa CM.ÊPA! — Criação Musical, Experimentação e Pesquisa Artística (UFSM/CNPq), pelo Dr. Paulo Rios Filho.

O programa foi escrito em linguagem Python, com apoio de agentes de inteligência artificial generativa no processo de elaboração, revisão, depuração e refinamento do código. Foram utilizados Claude Sonnet 4.6, da Anthropic, e GPT-5.5 Thinking, da OpenAI/ChatGPT, como assistentes de programação. A concepção do script, a definição de suas funcionalidades, a orientação das soluções, os testes práticos, a revisão crítica e as decisões finais de implementação foram conduzidos pelo agente humano responsável pelo projeto.

Grupo de pesquisa CM.ÊPA! — Criação Musical, Experimentação e Pesquisa Artística:
https://www.ufsm.br/grupos/cmepa

English version
===============

MS Capture — clickable launcher for Windows
==========================================

Description
-----------

MS Capture is a Python script for capturing and exporting excerpts from MuseScore 4 scores, approximating the screenshot/camera functionality formerly available in MuseScore 3. The app allows selected score excerpts to be exported as SVG, PNG, or PDF, with resolution and transparency options when applicable.

Contents of this folder
-----------------------

1. ABRIR_ms_capture.vbs
   - Double-click this file to open the app without PowerShell and without a console window.

2. ABRIR_ms_capture_COM_DIAGNOSTICO.bat
   - Use this file if the .vbs launcher does not open anything. It displays error messages in a terminal window.

3. ms_capture_v4.py
   - Main Python script.

4. ms_capture_v4.pyw
   - Copy of the script using the .pyw extension. In some Windows installations, double-clicking this file also opens the app directly.

How to use
----------

1. Extract the entire ZIP file to a folder, for example:
   C:\Users\YOUR_USERNAME\Documents\MS_Capture_App

2. Do not move the launcher out of the folder unless you also move the ms_capture_v4.py file with it.

3. Double-click:
   ABRIR_ms_capture.vbs

Requirements
------------

- Python 3 installed on Windows.
- Tkinter available in the Python installation.
- MuseScore 4 installed.

Note
----

This is not a standalone .exe file. It is a clickable launcher for the Python script. To create a standalone .exe, the recommended path is to package the app with PyInstaller on the Windows system where MuseScore and Python are installed.

Credits and development
-----------------------

This script was developed within the research group CM.ÊPA! — Musical Creation, Experimentation, and Artistic Research (UFSM/CNPq), by Dr. Paulo Rios Filho.

The program was written in the Python programming language, with support from generative artificial intelligence agents during the process of drafting, reviewing, debugging, and refining the code. Claude Sonnet 4.6, by Anthropic, and GPT-5.5 Thinking, by OpenAI/ChatGPT, were used as programming assistants. The conception of the script, the definition of its functionalities, the guidance of technical solutions, practical testing, critical review, and final implementation decisions were conducted by the human agent responsible for the project.

CM.ÊPA! — Musical Creation, Experimentation, and Artistic Research:
https://www.ufsm.br/grupos/cmepa
