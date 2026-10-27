# Monitor flutuante

Linha flutuante com CPU, RAM e GPU, lida a cada 2 s:

```
⠿ CPU  29% 56° │ RAM 8.9/23.3G  38% │ GPU  27% 45° 0.8G
```

Python + GTK3 do próprio Ubuntu. Nenhum pacote extra. ~71 MB de RAM, CPU perto de zero.

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

## Requisitos

Ubuntu/GNOME em X11, Python 3 do sistema com GTK3 (`python3-gi`, `gir1.2-gtk-3.0`). Nada de pip.
GPU NVIDIA é lida pelo driver (`libnvidia-ml.so.1`); sem GPU o bloco some.

## Instalar / remover

```bash
./instalar.sh                  # atalho no menu de apps + abre no login
./instalar.sh --sem-autostart  # só o atalho
./instalar.sh --remover        # tira atalho e autostart
./verifica.sh                  # confere sensores sem abrir janela
```

Rodar na mão: `./monitor_flutuante.py`. Se já estiver aberto, só mostra a janela.

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
