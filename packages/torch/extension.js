// SPDX-License-Identifier: GPL-2.0-only
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {QuickSlider, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const emitters = ['white:flash-0', 'white:flash-1'];
const base = '/sys/class/leds';
const chinese = /^zh([_.@-]|$)/i.test(GLib.get_language_names()[0]);
const label = chinese ? '手电筒' : 'Torch';

function level(name, attribute) {
    try {
        const [, data] = GLib.file_get_contents(`${base}/${name}/${attribute}`);
        return Number.parseInt(new TextDecoder().decode(data), 10);
    } catch {
        return NaN;
    }
}

function writeLevel(name, value) {
    return new Promise((resolve, reject) => {
        Gio.DBus.system.call('org.freedesktop.login1',
            '/org/freedesktop/login1/session/auto', 'org.freedesktop.login1.Session',
            'SetBrightness', new GLib.Variant('(ssu)', ['leds', name, value]),
            null, Gio.DBusCallFlags.NONE, 2000, null, (bus, result) => {
                try {
                    bus.call_finish(result);
                    resolve();
                } catch (error) {
                    reject(error);
                }
            });
    });
}

function waitForController() {
    return new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, 90, () => {
        resolve();
        return GLib.SOURCE_REMOVE;
    }));
}

const TorchSlider = GObject.registerClass(class TorchSlider extends QuickSlider {
    _init(limits) {
        super._init({iconName: 'media-flash-symbolic', menuEnabled: false});
        this.slider.accessible_name = label;
        this._limits = limits;
        this._target = 0;
        this._sync();
        this._sliderSignal = this.slider.connect('notify::value', () => {
            this._target = this.slider.value;
            this._cancelTimer();
            // Each write briefly blanks the PMIC outputs. Coalesce slider motion.
            this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 220, () => {
                this._timer = 0;
                this._apply();
                return GLib.SOURCE_REMOVE;
            });
        });
        this.connect('icon-clicked', () => {
            this.slider.value = this.slider.value > 0 ? 0 : 0.33;
            this._cancelTimer();
            this._apply();
        });
    }

    _cancelTimer() {
        if (this._timer) {
            GLib.Source.remove(this._timer);
            this._timer = 0;
        }
    }

    _sync() {
        if (this._sliderSignal)
            GObject.signal_handler_block(this.slider, this._sliderSignal);
        const current = Math.min(...emitters.map((name, i) => level(name, 'brightness') / this._limits[i]));
        this.slider.value = Number.isFinite(current) ? Math.min(current, 1) : 0;
        this._target = this.slider.value;
        if (this._sliderSignal)
            GObject.signal_handler_unblock(this.slider, this._sliderSignal);
    }

    async _apply() {
        if (this._writing)
            return;
        this._writing = true;
        try {
            let target;
            do {
                target = this._target;
                for (const [i, name] of emitters.entries()) {
                    if (target !== this._target)
                        break;
                    const value = Math.round(target * this._limits[i]);
                    if (level(name, 'brightness') === value)
                        continue;
                    await writeLevel(name, value);
                    await waitForController();
                }
            } while (target !== this._target);
        } catch (error) {
            // Clear both outputs after a partial write.
            for (const name of emitters) {
                try {
                    await writeLevel(name, 0);
                    await waitForController();
                } catch {}
            }
            if (!this._closed) {
                this._cancelTimer();
                this._sync();
                Main.notifyError(label, error.message);
            }
        } finally {
            this._writing = false;
        }
    }

    destroy() {
        this._cancelTimer();
        this._closed = true;
        this._target = 0;
        this._apply();
        super.destroy();
    }
});

export default class TorchExtension extends Extension {
    enable() {
        const limits = emitters.map(name => Math.floor(level(name, 'max_brightness') * 0.8));
        if (!limits.every(value => value > 0))
            return;
        this._indicator = new SystemIndicator();
        this._indicator.quickSettingsItems.push(new TorchSlider(limits));
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
    }

    disable() {
        this._indicator?.quickSettingsItems.forEach(item => item.destroy());
        this._indicator?.destroy();
        this._indicator = null;
    }
}
