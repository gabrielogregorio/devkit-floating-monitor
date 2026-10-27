#!/usr/bin/env python3
"""Monitor flutuante: CPU, RAM e GPU numa linha, sobre a tela.

Leve de propósito: lê /proc e /sys direto, GPU NVIDIA via NVML (ctypes,
sem nvidia-smi), redesenha só quando o texto muda, tick de 2 s.
"""
import ctypes
import json
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    AppIndicator = None

APP_ID = "br.local.MonitorFlutuante"
CONFIG_DIR = os.path.expanduser("~/.config/monitor-flutuante")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
ICONES_DIR = os.path.expanduser("~/.cache/monitor-flutuante/icones")
# autostart passa --desligado: sobe só o ícone (cinza), linha oculta e sem leitura
DESLIGADO_NO_INICIO = "--desligado" in sys.argv


def gerar_icones():
    """Ícone 22x22 da barra: 3 barras (CPU/RAM/GPU). Colorido = ligado, cinza = desligado."""
    os.makedirs(ICONES_DIR, exist_ok=True)
    barras = ((3, 9), (9, 4), (15, 12))  # (x, topo)
    for estado, cores in (("on", ("#2ecc71", "#3498db", "#e67e22")),
                          ("off", ("#9a9a9a", "#9a9a9a", "#9a9a9a"))):
        corpo = "".join(f'<rect x="{x}" y="{y}" width="4.5" height="{19 - y}" rx="1" fill="{c}"/>'
                        for (x, y), c in zip(barras, cores))
        with open(os.path.join(ICONES_DIR, f"monitor-flutuante-{estado}.svg"), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" '
                    f'viewBox="0 0 22 22">{corpo}</svg>')
INTERVALO_S = 2
VERMELHO = "#ff4d4d"
GRIP = "⠿ "
SOMBRA = "rgba(0,0,0,0.9)"
CSS = f"""
#monitor {{ background-color: transparent; }}
.caixa {{ padding: 3px 8px; border-radius: 6px; background-color: rgba(18,18,23,0); }}
.caixa.solido {{ background-color: rgba(18,18,23,0.78); }}
.caixa.hover {{ background-color: rgba(18,18,23,0.40); }}
.caixa.solido.hover {{ background-color: rgba(18,18,23,0.88); }}
.caixa label {{
  color: #ffffff; font-family: monospace; font-weight: bold; font-size: 10pt;
  text-shadow: 1px 1px 0 {SOMBRA}, -1px -1px 0 {SOMBRA}, 1px -1px 0 {SOMBRA}, -1px 1px 0 {SOMBRA};
}}
.caixa .grip {{ opacity: 0.9; }}
.caixa.travado .grip {{ opacity: 0.35; }}
.caixa.pausado .texto {{ opacity: 0.55; }}
"""

PADRAO = {
    "x": None,
    "y": None,
    "sempre_acima": True,
    "transparente": True,
    "travado": False,
    "visivel": True,
    "limite_uso": 80,
    "limite_temp_cpu": 85,
    "limite_temp_gpu": 83,
}


def carregar_config():
    cfg = dict(PADRAO)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def salvar_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------- sensores

class Cpu:
    def __init__(self):
        self.ant = self._ler()
        self.temp_path = self._achar_temp()

    @staticmethod
    def _ler():
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
        ocioso = v[3] + v[4]  # idle + iowait
        return sum(v), ocioso

    def uso(self):
        total, ocioso = self._ler()
        dt, di = total - self.ant[0], ocioso - self.ant[1]
        self.ant = (total, ocioso)
        return 0.0 if dt <= 0 else 100.0 * (dt - di) / dt

    @staticmethod
    def _achar_temp():
        base = "/sys/class/hwmon"
        try:
            hwmons = sorted(os.listdir(base))
        except OSError:
            return None
        for preferido in ("k10temp", "zenpower", "coretemp", "cpu_thermal"):
            for h in hwmons:
                d = os.path.join(base, h)
                try:
                    with open(os.path.join(d, "name")) as f:
                        if f.read().strip() != preferido:
                            continue
                except OSError:
                    continue
                # Tctl (AMD) ou Package id 0 (Intel); senão temp1
                for arq in sorted(os.listdir(d)):
                    if arq.startswith("temp") and arq.endswith("_label"):
                        with open(os.path.join(d, arq)) as f:
                            if f.read().strip() in ("Tctl", "Tdie", "Package id 0"):
                                return os.path.join(d, arq.replace("_label", "_input"))
                t1 = os.path.join(d, "temp1_input")
                if os.path.exists(t1):
                    return t1
        return None

    def temp(self):
        if not self.temp_path:
            return None
        try:
            with open(self.temp_path) as f:
                return int(f.read()) / 1000.0
        except (OSError, ValueError):
            return None


def ler_ram():
    info = {}
    with open("/proc/meminfo") as f:
        for linha in f:
            k, v = linha.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                info[k] = int(v.split()[0]) * 1024
                if len(info) == 2:
                    break
    total = info["MemTotal"]
    usado = total - info["MemAvailable"]
    return usado, total, 100.0 * usado / total


class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Mem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


class Gpu:
    """NVIDIA via NVML; AMD/Intel via sysfs (gpu_busy_percent). None se nada."""

    def __init__(self):
        self.nv = None
        self.handle = ctypes.c_void_p()
        self.amd = None
        try:
            nv = ctypes.CDLL("libnvidia-ml.so.1")
            if nv.nvmlInit_v2() == 0 and nv.nvmlDeviceGetHandleByIndex_v2(
                    0, ctypes.byref(self.handle)) == 0:
                self.nv = nv
        except OSError:
            pass
        if not self.nv:
            for card in sorted(os.listdir("/sys/class/drm")):
                p = f"/sys/class/drm/{card}/device/gpu_busy_percent"
                if os.path.exists(p):
                    self.amd = p
                    break

    @property
    def existe(self):
        return bool(self.nv or self.amd)

    def ler(self):
        """(uso %, temp °C, vram usada, vram total)"""
        if self.nv:
            u, m, t = _Util(), _Mem(), ctypes.c_uint()
            uso = u.gpu if self.nv.nvmlDeviceGetUtilizationRates(
                self.handle, ctypes.byref(u)) == 0 else None
            temp = t.value if self.nv.nvmlDeviceGetTemperature(
                self.handle, 0, ctypes.byref(t)) == 0 else None
            if self.nv.nvmlDeviceGetMemoryInfo(self.handle, ctypes.byref(m)) == 0:
                return uso, temp, m.used, m.total
            return uso, temp, None, None
        if self.amd:
            try:
                with open(self.amd) as f:
                    return int(f.read()), None, None, None
            except (OSError, ValueError):
                pass
        return None, None, None, None

    def fechar(self):
        if self.nv:
            self.nv.nvmlShutdown()


# --------------------------------------------------------------------- app

def gb(n):
    return f"{n / 1024 ** 3:.1f}"


class Monitor(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None

    # ---- ciclo de vida
    def do_activate(self):
        if self.win:  # segunda instância (atalho/menu): liga
            self.ligar(True)
            return
        self.hold()
        self.cfg = carregar_config()
        self.cpu = Cpu()
        self.gpu = Gpu()
        self.pausado = False
        self.hover = False
        self.markup = ""
        self.timer = None
        self._salvar_id = None

        self._criar_janela()
        self._criar_bandeja()
        self.cpu.uso()  # descarta a 1ª amostra (sem delta)
        self.atualizar()
        self._ligar_timer()
        # autostart sobe desligado; abrir pelo atalho é pedir pra ligar
        self.ligar(not DESLIGADO_NO_INICIO)

    def sair(self, *_):
        self._salvar_posicao()
        self.gpu.fechar()
        self.release()
        self.quit()

    # ---- janela
    def _criar_janela(self):
        w = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        w.set_application(self)
        w.set_name("monitor")
        w.set_title("Monitor flutuante")
        w.set_decorated(False)
        w.set_resizable(False)  # encolhe/estica junto com o texto
        w.set_skip_taskbar_hint(True)
        w.set_skip_pager_hint(True)
        w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        w.set_accept_focus(False)
        w.stick()  # aparece em todos os workspaces
        w.set_keep_above(self.cfg["sempre_acima"])
        visual = w.get_screen().get_rgba_visual()
        if visual:
            w.set_visual(visual)
        w.connect("configure-event", self._movido)
        w.connect("delete-event", lambda *_: self.mostrar(False) or True)

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            w.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.grip = Gtk.Label(label=GRIP)
        self.grip.get_style_context().add_class("grip")
        self.texto = Gtk.Label()
        self.texto.get_style_context().add_class("texto")
        caixa = Gtk.Box(spacing=0)
        caixa.get_style_context().add_class("caixa")
        caixa.pack_start(self.grip, False, False, 0)
        caixa.pack_start(self.texto, False, False, 0)

        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        ev.connect("button-press-event", self._clique)
        ev.connect("enter-notify-event", self._hover, True)
        ev.connect("leave-notify-event", self._hover, False)
        ev.add(caixa)
        w.add(ev)
        self.caixa = caixa
        self.win = w
        self._aplicar_estilo()

    def _aplicar_estilo(self):
        st = self.caixa.get_style_context()
        for classe, ligado in (("solido", not self.cfg["transparente"]),
                               ("hover", self.hover),
                               ("travado", self.cfg["travado"]),
                               ("pausado", self.pausado)):
            (st.add_class if ligado else st.remove_class)(classe)

    def _posicionar(self):
        x, y = self.cfg["x"], self.cfg["y"]
        if x is None or y is None:
            geo = Gdk.Display.get_default().get_primary_monitor() \
                or Gdk.Display.get_default().get_monitor(0)
            r = geo.get_workarea()
            larg = self.win.get_size()[0]
            x, y = r.x + r.width - larg - 16, r.y + 8
        self.win.move(x, y)

    def _hover(self, _w, ev, dentro):
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False  # entrou/saiu de um filho, não da janela
        self.hover = dentro
        self._aplicar_estilo()
        return False

    def _clique(self, w, ev):
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return True
        no_grip = ev.x < self.grip.get_allocation().x + self.grip.get_allocated_width()
        if ev.button == 1 and no_grip and not self.cfg["travado"]:
            self.win.begin_move_drag(ev.button, int(ev.x_root), int(ev.y_root), ev.time)
        else:
            menu = self._menu()
            menu.attach_to_widget(w, None)
            menu.popup_at_pointer(ev)
        return True

    def _movido(self, w, _ev):
        if self._salvar_id:
            GLib.source_remove(self._salvar_id)
        self._salvar_id = GLib.timeout_add(800, self._salvar_posicao)
        return False

    def _salvar_posicao(self):
        self._salvar_id = None
        if self.win and self.win.get_visible():
            self.cfg["x"], self.cfg["y"] = self.win.get_position()
        salvar_config(self.cfg)
        return False

    # ---- leitura
    def _ligar_timer(self):
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(INTERVALO_S, self.atualizar)

    def atualizar(self):
        if self.pausado:
            self.timer = None
            return False
        c = self.cfg
        lim = c["limite_uso"]

        def seg(txt, alerta):
            return f'<span foreground="{VERMELHO}">{txt}</span>' if alerta else txt

        partes = []
        cpu = self.cpu.uso()
        tc = self.cpu.temp()
        t = f"CPU {cpu:3.0f}%" + (f" {tc:.0f}°" if tc is not None else "")
        partes.append(seg(t, cpu >= lim or (tc is not None and tc >= c["limite_temp_cpu"])))

        usado, total, pct = ler_ram()
        t = f"RAM {gb(usado)}/{gb(total)}G {pct:3.0f}%"
        partes.append(seg(t, pct >= lim))

        if self.gpu.existe:
            uso, tg, vu, vt = self.gpu.ler()
            t = "GPU " + ("--" if uso is None else f"{uso:3d}%")
            alerta = (uso or 0) >= lim
            if tg is not None:
                t += f" {tg}°"
                alerta = alerta or tg >= c["limite_temp_gpu"]
            if vu is not None and vt:
                t += f" {gb(vu)}G"
                alerta = alerta or 100.0 * vu / vt >= lim
            partes.append(seg(t, alerta))
    
        self._aplicar_texto(" │ ".join(partes))
        return True

    def _aplicar_texto(self, markup):
        if markup != self.markup:  # nada mudou: não redesenha
            self.markup = markup
            self.texto.set_markup(markup)

    # ---- ações
    def mostrar(self, vis):
        self.cfg["visivel"] = vis
        if vis:
            self.win.show_all()
            self._posicionar()
            self.win.set_keep_above(self.cfg["sempre_acima"])
        else:
            self._salvar_posicao()
            self.win.hide()
        salvar_config(self.cfg)
        self._atualizar_bandeja()

    def ligado(self):
        return bool(self.win and self.win.get_visible()) and not self.pausado

    def ligar(self, on):
        """Ligado = linha visível e lendo. Desligado = oculta e sem timer (só o ícone fica)."""
        if on:
            if self.pausado:
                self.pausar()
            self.mostrar(True)
        else:
            if not self.pausado:
                self.pausar()
            self.mostrar(False)

    def alternar(self, chave):
        self.cfg[chave] = not self.cfg[chave]
        if chave == "sempre_acima":
            self.win.set_keep_above(self.cfg[chave])
        salvar_config(self.cfg)
        self._aplicar_estilo()
        self._atualizar_bandeja()

    def pausar(self, *_):
        self.pausado = not self.pausado
        if self.pausado:
            if self.timer:
                GLib.source_remove(self.timer)
                self.timer = None
        else:
            self.cpu.uso()
            self.atualizar()
            self._ligar_timer()
        self._aplicar_estilo()
        self._atualizar_bandeja()

    def abrir_monitor(self, *_):
        for cmd in (["gnome-system-monitor"], ["plasma-systemmonitor"],
                    ["xfce4-taskmanager"], ["x-terminal-emulator", "-e", "htop"]):
            try:
                subprocess.Popen(cmd, start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue

    # ---- menu (mesmo menu na janela e na barra superior)
    def _menu(self):
        m = Gtk.Menu()

        def item(rotulo, cb):
            i = Gtk.MenuItem(label=rotulo)
            i.connect("activate", cb)
            m.append(i)

        def check(rotulo, ativo, cb):
            i = Gtk.CheckMenuItem(label=rotulo)
            i.set_active(ativo)
            i.connect("toggled", cb)
            m.append(i)

        check("Ligado", self.ligado(), lambda w: self.ligar(w.get_active()))
        m.append(Gtk.SeparatorMenuItem())
        check("Sempre acima de tudo", self.cfg["sempre_acima"],
              lambda *_: self.alternar("sempre_acima"))
        check("Transparente (texto branco)", self.cfg["transparente"],
              lambda *_: self.alternar("transparente"))
        check("Travar posição", self.cfg["travado"],
              lambda *_: self.alternar("travado"))
        check("Pausar leitura", self.pausado, self.pausar)
        item("Voltar pro canto da tela", self._resetar_posicao)
        m.append(Gtk.SeparatorMenuItem())
        item("Abrir Monitor do Sistema", self.abrir_monitor)
        # sem "Sair" de propósito: o ícone fica sempre na barra; "Ligado" desmarcado é o desligar
        m.show_all()
        return m

    def _resetar_posicao(self, *_):
        self.cfg["x"] = self.cfg["y"] = None
        self._posicionar()

    # ---- barra superior
    def _criar_bandeja(self):
        self.ind = self.icone = None
        gerar_icones()
        if AppIndicator:
            self.ind = AppIndicator.Indicator.new(
                "monitor-flutuante", "monitor-flutuante-on",
                AppIndicator.IndicatorCategory.SYSTEM_SERVICES)
            self.ind.set_icon_theme_path(ICONES_DIR)
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            self.ind.set_title("Monitor flutuante")
            self._atualizar_bandeja()
        else:
            # fallback: ícone legado, a extensão ubuntu-appindicators exibe no topo
            icone = Gtk.StatusIcon.new_from_file(os.path.join(ICONES_DIR, "monitor-flutuante-on.svg"))
            icone.set_tooltip_text("Monitor flutuante")
            icone.set_title("Monitor flutuante")
            icone.connect("activate", lambda *_: self.ligar(not self.ligado()))
            icone.connect("popup-menu", self._menu_icone)
            self.icone = icone

    def _menu_icone(self, icone, botao, tempo):
        self._menu_bandeja = self._menu()
        self._menu_bandeja.popup(None, None, Gtk.StatusIcon.position_menu, icone, botao, tempo)

    def _atualizar_bandeja(self):
        estado = "on" if self.ligado() else "off"
        if self.icone:
            self.icone.set_from_file(os.path.join(ICONES_DIR, f"monitor-flutuante-{estado}.svg"))
        if self.ind:
            self.ind.set_icon_full(f"monitor-flutuante-{estado}",
                                   "Monitor flutuante: " + ("ligado" if estado == "on" else "desligado"))
            self._menu_bandeja = self._menu()
            self.ind.set_menu(self._menu_bandeja)


def main():
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)  # Gtk.StatusIcon
    GLib.set_prgname("monitor-flutuante")
    Monitor().run([a for a in sys.argv if a != "--desligado"])  # GApplication recusa opção desconhecida


if __name__ == "__main__":
    main()
