# -*- coding: utf-8 -*-
#
# GPL License and Copyright Notice ============================================
#  This file is part of Wrye Bash.
#
#  Wrye Bash is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  Wrye Bash is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Wrye Bash; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#  Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2015 Wrye Bash Team
#  https://github.com/wrye-bash
#
# =============================================================================
import wx as _wx

# Base elements ---------------------------------------------------------------
class Widget(object):
    """Base class for all GUI items."""
    def __init__(self):
        self._native_widget = None  # type: _wx.Window

    @property
    def enabled(self): return self._native_widget.IsEnabled()
    @enabled.setter
    def enabled(self, enabled):
        # type: (bool) -> None
        self._native_widget.Enable(enabled)

    @property
    def tooltip(self):
        return self._native_widget.GetToolTipString()
    @tooltip.setter
    def tooltip(self, text):
        if not text:
            self._native_widget.UnsetToolTip()
        else:
            self._native_widget.SetToolTip(text)

# Buttons ---------------------------------------------------------------------
class _AbstractButton(Widget): pass

class Button(_AbstractButton):
    _id = _wx.ID_ANY
    default_label = u''
    def __init__(self, parent, label=u'', on_click=None, tooltip=None,
                 default=False):
        super(Button, self).__init__()
        if not label and self.__class__.default_label:
            label = self.__class__.default_label
        self._native_widget = _wx.Button(parent, self.__class__._id,
                                         label=label, name=u'button')
        if on_click:
            self._native_widget.Bind(_wx.EVT_BUTTON, lambda __evt: on_click)
        if default:
            self._native_widget.SetDefault()
        if tooltip:
            self.tooltip = tooltip

class OkButton(Button): _id = _wx.ID_OK
class CancelButton(Button):
    _id = _wx.ID_CANCEL
    default_label = _(u'Cancel')
class SaveButton(Button):
    _id = _wx.ID_SAVE
    default_label = _(u'Save')
class SaveAsButton(Button): _id = _wx.ID_SAVEAS
class RevertButton(Button): _id = _wx.ID_SAVE
class RevertToSavedButton(Button): _id = _wx.ID_REVERT_TO_SAVED
class OpenButton(Button): _id = _wx.ID_OPEN
class SelectAllButton(Button): _id = _wx.ID_SELECTALL
class ApplyButton(Button): _id = _wx.ID_APPLY

class ToggleButton(_AbstractButton):
    def __init__(self, parent, label=u'', on_toggle=None, tooltip=None):
        super(ToggleButton, self).__init__()
        self._native_widget = _wx.ToggleButton(parent, _wx.ID_ANY,
                                               label=label, name=u'button')
        if on_toggle:
            def _toggle_callback(event):
                on_toggle(self._native_widget.GetValue())
            self._native_widget.Bind(_wx.EVT_TOGGLEBUTTON, _toggle_callback)
        if tooltip:
            self.tooltip = tooltip

    @property
    def toggled(self): return self._native_widget.GetValue()
    @toggled.setter
    def toggled(self, value):
        # type: (bool) -> None
        self._native_widget.SetValue(value)

class CheckBox(_AbstractButton):
    def __init__(self, parent, label=u'', on_toggle=None, tooltip=None,
                 checked=False):
        super(CheckBox, self).__init__()
        self._native_widget = _wx.CheckBox(parent, _wx.ID_ANY,
                                           label=label, name=u'checkBox')
        if on_toggle:
            def _toggle_callback(event):
                on_toggle(self._native_widget.GetValue())
            self._native_widget.Bind(_wx.EVT_CHECKBOX, _toggle_callback)
        if tooltip:
            self.tooltip = tooltip
        self.checked = checked

    @property
    def checked(self): return self._native_widget.GetValue()
    @checked.setter
    def checked(self, value):
        # type: (bool) -> None
        self._native_widget.SetValue(value)

