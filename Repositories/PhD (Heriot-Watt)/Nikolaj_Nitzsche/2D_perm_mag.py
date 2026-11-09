"""
Interactive magnetic field viewer for a uniformly magnetized cylinder.

Click anywhere on the plot to see the exact position, |B|, B_x, and B_z
at that point. Field is computed via the closed-form elliptic-integral
solution for a single current loop (Simpson et al. form), stacked
numerically along the magnet's length to model the finite cylinder.

Requirements:
    pip install numpy scipy matplotlib

Run:
    python interactive_magnet_field.py
"""

import numpy as np
from scipy.special import ellipk, ellipe
from scipy.integrate import quad
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.widgets import TextBox, Button

mu0 = 4 * np.pi * 1e-7  # vacuum permeability [T*m/A]

# Typical remanence (Br) ranges for sintered NdFeB grades [T]
GRADE_BR = {
    "N35": (1.17, 1.22),
    "N38": (1.22, 1.25),
    "N42": (1.29, 1.32),
    "N45": (1.32, 1.38),
    "N52": (1.43, 1.47),
}


def magnetization_from_grade(grade, Br_override=None):
    """
    Convert a magnet grade to magnetization M [A/m].
    Pass Br_override [T] to use a specific manufacturer value instead
    of the generic spec-range midpoint (e.g. K&J Magnetics uses ~1.327 T
    for N42 -- check your own supplier's datasheet for best accuracy).
    """
    if Br_override is not None:
        Br = Br_override
    else:
        lo, hi = GRADE_BR[grade]
        Br = 0.5 * (lo + hi)
    return Br / mu0, Br


def loop_field(rho, z, a, dI):
    """
    Off-axis magnetic field of a single circular current loop.
    rho, z: observation point in cylindrical coordinates [m]
    a: loop radius [m]
    dI: loop current [A]
    Returns (B_rho, B_z) in Tesla. Vectorized over rho, z (numpy arrays).
    """
    rho_safe = np.where(np.abs(rho) < 1e-12, 1e-12, rho)

    k2 = 4 * a * rho_safe / ((a + rho_safe) ** 2 + z ** 2)
    k2 = np.clip(k2, 0, 1 - 1e-15)

    K = ellipk(k2)
    E = ellipe(k2)

    denom1 = (a + rho_safe) ** 2 + z ** 2
    denom2 = (a - rho_safe) ** 2 + z ** 2

    B_rho = (mu0 * dI / (2 * np.pi)) * (z / (rho_safe * np.sqrt(denom1))) * (
        -K + (a ** 2 + rho_safe ** 2 + z ** 2) / denom2 * E
    )
    B_z = (mu0 * dI / (2 * np.pi)) * (1 / np.sqrt(denom1)) * (
        K + (a ** 2 - rho_safe ** 2 - z ** 2) / denom2 * E
    )

    B_rho = np.where(np.abs(rho) < 1e-12, 0.0, B_rho)
    return B_rho, B_z


def cylinder_field(rho, z, R, L, M):
    """
    Exact field of the finite cylinder at a single point (rho, z),
    via numerical stacking of current loops (dI = M dz') along z' in
    [-L/2, L/2]. Returns (B_rho, B_z) in Tesla.
    """
    def integrand_rho(zp):
        Brho, _ = loop_field(rho, z - zp, R, M)
        return Brho

    def integrand_z(zp):
        _, Bz = loop_field(rho, z - zp, R, M)
        return Bz

    Brho_total, _ = quad(integrand_rho, -L / 2, L / 2, limit=200)
    Bz_total, _ = quad(integrand_z, -L / 2, L / 2, limit=200)
    return Brho_total, Bz_total


def field_at_xz(x, z, R, L, M):
    """
    Field at a Cartesian point (x, z) in the x-z plane (y=0).
    Returns (Bx, Bz) in Tesla. B_x = sign(x) * B_rho since rho-hat
    aligns with +/- x-hat in this plane.
    """
    rho = abs(x)
    Brho, Bz = cylinder_field(rho, z, R, L, M)
    Bx = np.sign(x) * Brho if x != 0 else 0.0
    return Bx, Bz


def field_grid_xz(R, L, M, x_range, z_range, nx=90, nz=90):
    """Precompute Bx, Bz on a grid for the background image and streamlines."""
    xs = np.linspace(*x_range, nx)
    zs = np.linspace(*z_range, nz)
    Bx = np.zeros((nz, nx))
    Bz = np.zeros((nz, nx))

    for i, z in enumerate(zs):
        for j, x in enumerate(xs):
            bx, bz = field_at_xz(x, z, R, L, M)
            Bx[i, j] = bx
            Bz[i, j] = bz

    return xs, zs, Bx, Bz


class InteractiveFieldPlot:
    """Click-to-inspect wrapper around the field plot."""

    def __init__(self, R, L, M, grade_label="", nx=90, nz=90):
        self.R = R
        self.L = L
        self.M = M
        self.grade_label = grade_label

        margin = 10 * R
        self.x_range = (-(R + margin), R + margin)
        self.z_range = (-(L / 2 + margin), L / 2 + margin)

        print("Computing field grid (this can take a few seconds)...")
        self.xs, self.zs, self.Bx, self.Bz = field_grid_xz(
            R, L, M, self.x_range, self.z_range, nx=nx, nz=nz
        )
        self.Bmag = np.sqrt(self.Bx ** 2 + self.Bz ** 2)

        self._build_plot()

    def _build_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(8.5, 8.5))
        self.fig.subplots_adjust(bottom=0.18)

        Bmag_G = self.Bmag * 1e4  # Tesla -> Gauss
        self.pcm = self.ax.pcolormesh(
            self.xs * 1000, self.zs * 1000, Bmag_G,
            shading="gouraud", cmap="turbo",
            norm=mcolors.LogNorm(vmin=max(Bmag_G.min(), 1), vmax=Bmag_G.max()),
        )
        self.fig.colorbar(self.pcm, ax=self.ax, label="|B| [Gauss]")

        self.ax.streamplot(
            self.xs * 1000, self.zs * 1000, self.Bx, self.Bz,
            color="dimgray", density=1.6, linewidth=0.9, arrowsize=1.2,
        )

        R_mm, L_mm = self.R * 1000, self.L * 1000
        self.ax.plot(
            [-R_mm, -R_mm, R_mm, R_mm, -R_mm],
            [-L_mm / 2, L_mm / 2, L_mm / 2, -L_mm / 2, -L_mm / 2],
            color="black", linewidth=1.5,
        )

        self.ax.set_xlabel("x [mm]")
        self.ax.set_ylabel("z [mm]")
        title = f"D={R_mm*2:.0f} mm, L={L_mm:.0f} mm"
        if self.grade_label:
            title = f"{self.grade_label} Magnet — {title}"
        self.ax.set_title(title + "\nClick anywhere to inspect the field")
        self.ax.set_aspect("equal")

        # Marker + text box for the clicked point, created empty and updated on click
        self.marker, = self.ax.plot([], [], "wo", markersize=8,
                                     markeredgecolor="black", zorder=10)
        self.text = self.ax.text(
            0.02, 0.98, "", transform=self.ax.transAxes,
            va="top", ha="left", fontsize=10, family="monospace",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
        )

        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self._build_coordinate_inputs()

    def _build_coordinate_inputs(self):
        self.x_box_ax = self.fig.add_axes([0.10, 0.03, 0.08, 0.04])
        self.z_box_ax = self.fig.add_axes([0.26, 0.03, 0.08, 0.04])
        self.button_ax = self.fig.add_axes([0.44, 0.03, 0.10, 0.04])

        self.x_box = TextBox(self.x_box_ax, "x [mm] ", initial="0")
        self.z_box = TextBox(self.z_box_ax, "z [mm] ", initial="0")
        self.compute_button = Button(self.button_ax, "Compute")

        self.x_box.on_submit(self._on_manual_input)
        self.z_box.on_submit(self._on_manual_input)
        self.compute_button.on_clicked(self._on_manual_input)

    def _update_point_info(self, x_mm, z_mm):
        x_m, z_m = x_mm / 1000, z_mm / 1000

        Bx, Bz = field_at_xz(x_m, z_m, self.R, self.L, self.M)
        Bmag = np.sqrt(Bx ** 2 + Bz ** 2)

        Bx_G, Bz_G, Bmag_G = Bx * 1e4, Bz * 1e4, Bmag * 1e4

        inside = abs(x_mm) <= self.R * 1000 and abs(z_mm) <= self.L * 1000 / 2
        location_note = " (inside magnet)" if inside else ""

        info = (
            f"Position: x={x_mm:7.2f} mm, z={z_mm:7.2f} mm{location_note}\n"
            f"|B|  = {Bmag_G:9.2f} G  ({Bmag:.4f} T)\n"
            f"B_x  = {Bx_G:9.2f} G  ({Bx:.4f} T)\n"
            f"B_z  = {Bz_G:9.2f} G  ({Bz:.4f} T)"
        )
        self.text.set_text(info)
        self.marker.set_data([x_mm], [z_mm])
        self.fig.canvas.draw_idle()

        print(info)
        print("-" * 50)

    def _on_click(self, event):
        if event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return

        x_mm, z_mm = event.xdata, event.ydata
        self._update_point_info(x_mm, z_mm)

    def _on_manual_input(self, event=None):
        try:
            x_mm = float(self.x_box.text)
            z_mm = float(self.z_box.text)
        except ValueError:
            print("Please enter valid numeric x and z coordinates.")
            return

        self._update_point_info(x_mm, z_mm)

    def show(self):
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    # ---- Configure your magnet here ----
    grade = "N42"
    R = 12.7e-3   # radius [m]
    L = 25.4e-3   # length [m]

    # Use Br_override to match a specific supplier's datasheet, e.g.:
    # M, Br = magnetization_from_grade(grade, Br_override=1.327)
    M, Br = magnetization_from_grade(grade)
    print(f"Grade {grade}: Br = {Br:.3f} T -> M = {M:.3e} A/m")

    viewer = InteractiveFieldPlot(R, L, M, grade_label=grade, nx=90, nz=90)
    viewer.show()