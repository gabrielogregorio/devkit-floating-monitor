<div align="center">

# Monitor flutuante

**CPU, RAM e GPU numa linha transparente por cima de tudo, com ícone na barra do GNOME.**

![Python](https://img.shields.io/badge/Python-3.12-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![GTK](https://img.shields.io/badge/GTK-3-4A86CF?style=for-the-badge&logo=gtk&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![GNOME](https://img.shields.io/badge/GNOME-X11-4A86CF?style=for-the-badge&logo=gnome&logoColor=white)
![Offline](https://img.shields.io/badge/100%25-local%20e%20offline-555555?style=for-the-badge)

</div>

## Sobre o projeto

Linha flutuante com CPU, RAM e GPU, lida a cada 2 s:

```
⠿ CPU  29% 56° │ RAM 8.9/23.3G  38% │ GPU  27% 45° 0.8G
```

Python + GTK3 do próprio Ubuntu. Nenhum pacote extra. ~71 MB de RAM, CPU perto de zero.

## Configurar num PC novo

Feito e testado em Ubuntu 24.04 + GNOME. Usa o Python do sistema: nada de pip, nada de venv.

1. Sessão **X11** (Xorg). No Ubuntu 24.04: tela de login → engrenagem no canto → "Ubuntu em Xorg". Em Wayland a janela não fica por cima e o mouse não é capturado.
2. Pacotes:
   ```bash
   sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
                    gnome-shell-extension-appindicator
   ```
   A extensão AppIndicator já vem ligada no Ubuntu. Em outro GNOME, ligue em *Extensões*
   (sem ela o ícone não aparece na barra superior).
3. Clonar e instalar:
   ```bash
   git clone <url-do-repo> devkit-monitor-flutuante
   cd devkit-monitor-flutuante
   ./instalar.sh        # atalho no menu de apps + início no login (sobe desligado: só o ícone)
   ./verifica.sh        # tem que terminar em OK
   ```
4. Ligar: ícone de barras na barra superior → **Ligado**. Ou abra "Monitor Flutuante" no menu.

**GPU:** NVIDIA é lida pelo driver proprietário (`libnvidia-ml.so.1`, vem no `nvidia-driver-*`).
Sem NVIDIA o bloco GPU some; AMD/Intel por `/sys` existe mas não foi testado.

**Fora do repositório** (o app cria sozinho):
`~/.config/monitor-flutuante/config.json` (posição e modos), `~/.cache/monitor-flutuante/icones/`,
`~/.local/share/applications/monitor-flutuante.desktop`, `~/.config/autostart/monitor-flutuante.desktop`.
Mudou a pasta de lugar? Rode `./instalar.sh` de novo: os atalhos guardam o caminho.

## Scripts disponíveis

```bash
# Rodar
./monitor_flutuante.py              # abre ligado (2ª execução só mostra a linha)
./monitor_flutuante.py --desligado  # só o ícone, como no login

# Instalar / remover atalhos e início no login
./instalar.sh
./instalar.sh --sem-autostart
./instalar.sh --remover

# Testar (sem abrir janela: lê os sensores uma vez e mostra a linha)
./verifica.sh
```

## Usar

| Ação | Como |
|---|---|
| Mover | segura no `⠿` e arrasta (a posição fica salva) |
| Menu | clique em qualquer ponto do texto |
| Ligar/desligar | menu do ícone da barra superior → "Ligado" |
| Menu pela barra | clique direito no ícone |

Opções do menu: sempre acima de tudo, transparente (texto branco), travar posição,
pausar leitura, voltar pro canto da tela, abrir Monitor do Sistema. "Ligado" liga/desliga
a linha (desligado = oculta e sem leitura). Não tem "Sair": o ícone fica sempre na barra
(colorido ligado, cinza desligado) e no login sobe desligado.

**Vermelho:** o bloco fica vermelho com uso >= 80% (CPU, RAM, GPU ou VRAM), CPU >= 85°C ou
GPU >= 83°C.

## Configurar

`~/.config/monitor-flutuante/config.json` (o menu grava sozinho; limites só por aqui):

```json
{ "limite_uso": 80, "limite_temp_cpu": 85, "limite_temp_gpu": 83 }
```

Editou? Sai pelo menu e abre de novo.

## Opcional

`sudo apt install gir1.2-ayatanaappindicator3-0.1` troca o ícone legado da barra pelo
indicador oficial do Ubuntu. O app detecta sozinho.

## Se der problema

- Não fica por cima: confira `echo $XDG_SESSION_TYPE`. Em `wayland` o GNOME não deixa;
  escolha "Ubuntu em Xorg" no login.
- Sumiu: clique no ícone da barra ou rode `./monitor_flutuante.py`.
- Foi parar fora da tela: menu do ícone → "Voltar pro canto da tela".

Detalhes técnicos e regras pra agente: `CLAUDE.md`.
