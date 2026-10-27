# CLAUDE.md - Monitor flutuante

Regras e contexto para qualquer agente que mexer neste projeto. Leia inteiro antes de
editar. Este diretório é autossuficiente: não depende de nenhum repo ou documento externo.

## O que é

Uma linha flutuante no desktop com CPU (% e temperatura), RAM (usada/total e %) e GPU
(%, temperatura e VRAM), atualizada a cada 2 s. Fica vermelha por bloco quando passa do
limite. Tem ícone na barra superior do GNOME e menu próprio no clique.

## Ambiente alvo

- Ubuntu 24.04, GNOME, **sessão X11** (`$XDG_SESSION_TYPE = x11`).
- Python 3 do sistema (`/usr/bin/python3`) + PyGObject + GTK3. **Nenhum pip, nenhuma venv.**
- GPU NVIDIA pelo driver proprietário (`libnvidia-ml.so.1`).
- Extensão `ubuntu-appindicators@ubuntu.com` ativa, com `legacy-tray-enabled = true`.
- **Não instalados**: `python3-gi-cairo`, `xdotool`, `wmctrl`.
  `gir1.2-ayatanaappindicator3-0.1` foi instalado em 2026-10-27 (indicador nativo).

## Regras do projeto

1. **Zero dependência nova.** Só biblioteca padrão + `gi` (Gtk/Gdk/GLib 3.0). Se uma
   mudança exigir pacote, escreva o `sudo apt install ...` e entregue pro usuário rodar; o
   código tem que continuar funcionando sem ele (fallback).
2. **Sem cairo.** O sinal `draw` com cairo quebra sem `python3-gi-cairo`. Visual é feito com
   `Gtk.Label` + CSS (classes ligadas/desligadas). Não reintroduza `draw`.
3. **Fixe as versões do gi** antes de importar (`Gtk 3.0` **e** `Gdk 3.0`). Sem o `Gdk`, o
   PyGObject carrega Gdk 4.0 e o app morre na importação.
4. **Leve de verdade.** Nada de subprocesso no tick (nada de `nvidia-smi`, `sensors`, `ps`).
   Ler `/proc` e `/sys` direto, GPU por NVML via `ctypes`. Redesenhar só se o texto mudou.
   Referência medida: ~71 MB RSS, CPU ~0.
5. **Uma linha só.** Novo dado entra como bloco `│ ...` na mesma linha, com regra de alerta.
6. **Não quebre o que o usuário configurou:** `~/.config/monitor-flutuante/config.json` guarda
   posição e modos. Chave nova entra em `PADRAO` (merge), nunca reescreva o arquivo do zero.
7. Nada de `rm` em arquivo do usuário: lixo vai para `./lixo/` (ignorado pelo git).

## Ligado/desligado (2026-10-27)

- **Sem item "Sair"**: o ícone fica sempre na barra. Desligar = desmarcar "Ligado"
  (linha oculta + timer parado). Ícone colorido ligado, cinza desligado
  (SVG gerado em `~/.cache/monitor-flutuante/icones/`).
- Autostart roda com `--desligado` (sobe só o ícone). Abrir pelo atalho = ligar.
  `--desligado` é tirado do argv antes do `run()`: GApplication recusa opção desconhecida.

## Arquitetura (`monitor_flutuante.py`, arquivo único)

| Parte | O que faz |
|---|---|
| `PADRAO`, `carregar_config`, `salvar_config` | config JSON com merge sobre os padrões; grava em `.tmp` + `os.replace` |
| `Cpu` | % por delta de `/proc/stat` (ocioso = idle + iowait); temp em hwmon (`k10temp`/`zenpower`/`coretemp`, label `Tctl`/`Tdie`/`Package id 0`), caminho resolvido uma vez |
| `ler_ram` | `/proc/meminfo`: usado = `MemTotal - MemAvailable` |
| `Gpu` | NVML por `ctypes` (`nvmlInit_v2`, `GetHandleByIndex_v2`, `GetUtilizationRates`, `GetTemperature`, `GetMemoryInfo`); fallback AMD/Intel em `/sys/class/drm/card*/device/gpu_busy_percent` (não testado); sem GPU o bloco some |
| `Monitor(Gtk.Application)` | instância única por `APP_ID`; 2ª execução só mostra a janela; `hold()` mantém vivo oculto |
| `_criar_janela` | janela sem borda, RGBA, UTILITY, `stick()`, `set_keep_above`, sem foco; `EventBox` → `Box.caixa` → label `⠿` + label do texto |
| `CSS` | fundo por classe (`solido`, `hover`, `travado`, `pausado`), texto branco com `text-shadow` de 4 lados, fonte monoespaçada |
| `_clique` | botão 1 sobre o `⠿` → `begin_move_drag`; qualquer outro clique → `Gtk.Menu.popup_at_pointer` |
| `_movido` / `_salvar_posicao` | salva posição com debounce de 800 ms |
| `atualizar` | tick de `INTERVALO_S`; monta markup Pango com `<span foreground=VERMELHO>` no bloco em alerta |
| `_menu` | o mesmo menu serve a janela e a barra superior (é recriado a cada abertura) |
| `_criar_bandeja` | `AyatanaAppIndicator3` se o typelib existir; senão `Gtk.StatusIcon` (esquerdo mostra/oculta, direito menu) |
| `abrir_monitor` | `gnome-system-monitor`, com fallbacks |

## Armadilhas já pagas (não repetir)

- `Requiring namespace 'Gdk' version '3.0', but '4.0' is already loaded` → faltou
  `gi.require_version("Gdk", "3.0")`.
- `Couldn't find foreign struct converter for 'cairo.Context'` → falta `python3-gi-cairo`;
  por isso não há cairo aqui.
- `Namespace AyatanaAppIndicator3 not available` → a `.so` existe, o typelib não; o fallback
  `StatusIcon` cobre.
- `pgrep -f "python3 monitor_flutuante.py"` acha o próprio shell do agente. O autostart roda
  como `/usr/bin/python3 <pasta>/monitor_flutuante.py --desligado`: use
  `pgrep -af monitor_flutuante | grep -v pgrep` e mate **pelo PID**, nunca com `pkill -f`.
- `set_keep_above` não funciona em Wayland (o compositor veta). Se a sessão virar Wayland,
  rodar com `GDK_BACKEND=x11` (XWayland). Não testado.
- GTK4 não serve: tirou `set_keep_above` e `StatusIcon`. Fique no GTK3.

## Como testar depois de mexer

1. `./verifica.sh` - compila, lê os sensores uma vez sem abrir janela, mostra a linha que
   seria exibida. Tem que sair `OK`.
2. Reiniciar a instância que está rodando (a nova não sobe se a antiga existir, por causa da
   instância única):
   ```bash
   PID=$(pgrep -f monitor_flutuante.py | head -1); [ -n "$PID" ] && kill "$PID"
   mkdir -p tmp && setsid /usr/bin/python3 "$PWD/monitor_flutuante.py" \
     > tmp/monitor-flutuante.log 2>&1 &
   ```
   Rode isso como script próprio, não colado num `bash -c` que contenha o nome do arquivo no
   padrão do `pgrep`.
3. Print do canto da tela sem ferramenta extra:
   ```bash
   python3 -c "import gi; gi.require_version('Gdk','3.0'); from gi.repository import Gdk
   r=Gdk.get_default_root_window(); w=r.get_width()
   Gdk.pixbuf_get_from_window(r,w-700,0,700,80).savev('tmp/monitor-print.png','png',[],[])"
   ```
4. Arrastar e menu não dão para testar por script (sem `xdotool`). Peça ao usuário.

## Arquivos

- `monitor_flutuante.py` - o app.
- `instalar.sh` - atalho em `~/.local/share/applications/` + autostart em
  `~/.config/autostart/` (`--sem-autostart`, `--remover`).
- `verifica.sh` - checagem rápida sem GUI.
- `LEIA-ME.md` - guia de uso.
- Fora daqui: `~/.config/monitor-flutuante/config.json` (estado), log de teste em
  `tmp/monitor-flutuante.log` (ignorado pelo git).

## Ideias não feitas (só se o usuário pedir)

- Limites editáveis pelo menu (hoje só no JSON).
- Click-through (input shape vazio no X11) para o texto não bloquear clique.
- Rede (KB/s) e disco como blocos extras.
- Ícone nativo: `sudo apt install gir1.2-ayatanaappindicator3-0.1` (o código já detecta).
