#
# Copyright (c) 2021 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from contextlib import contextmanager
import os
import time

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Ethtool
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import Veth

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.env import is_fedora
from .testlib.env import nm_major_minor_version

MAX_NETDEVSIM_WAIT_TIME = 5

TEST_NETDEVSIM_NIC = "sim0"


@contextmanager
def netdevsim_interface(ifname):
    try:
        cmdlib.exec_cmd("modprobe netdevsim".split(), check=True)
        with open("/sys/bus/netdevsim/new_device", "w") as fd:
            fd.write("1 1")

        done = False
        for i in range(0, MAX_NETDEVSIM_WAIT_TIME):
            time.sleep(1)
            i += 1
            nics = _get_cur_netdevsim_ifnames()
            if nics:
                _ip_iface_rename(nics[0], ifname)
                done = True
                break
        assert done
        yield
    finally:
        cmdlib.exec_cmd("modprobe -r netdevsim".split())


def _get_cur_netdevsim_ifnames():
    return os.listdir("/sys/devices/netdevsim1/net/")


def _ip_iface_rename(src_name, dst_name):
    cmdlib.exec_cmd(f"ip link set {src_name} down".split(), check=True)
    cmdlib.exec_cmd(
        f"ip link set {src_name} name {dst_name}".split(), check=True
    )


@pytest.mark.skipif(
    nm_major_minor_version() < 1.31
    or os.environ.get("CI") == "true"
    or not is_fedora(),
    reason=(
        "Ethtool pause test need NetworkManager 1.31+ and netdevsim kernel "
        "module"
    ),
)
def test_ethtool_pause_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: False,
                Ethtool.Pause.RX: True,
                Ethtool.Pause.TX: True,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.mark.skipif(
    nm_major_minor_version() < 1.31
    or os.environ.get("CI") == "true"
    or not is_fedora(),
    reason=(
        "Ethtool pause test need NetworkManager 1.31+ and netdevsim kernel "
        "module"
    ),
)
def test_ethtool_pause_auto_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: True,
                Ethtool.Pause.RX: True,
                Ethtool.Pause.TX: True,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=("CI does not have ethtool kernel option enabled"),
)
def test_ethtool_feature_using_ethtool_cli_alias_rx_checksumming(eth1_up):
    desire_iface_state = {
        Interface.NAME: "eth1",
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {"rx-checksumming": False}
        },
    }
    libnmstate.apply({Interface.KEY: [desire_iface_state]})

    desire_feature = desire_iface_state[Ethtool.CONFIG_SUBTREE][
        Ethtool.Feature.CONFIG_SUBTREE
    ]
    desire_feature.pop("rx-checksumming")
    desire_feature["rx-checksum"] = False

    assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})


def test_ethtool_invalid_feature(eth1_up):
    desire_iface_state = {
        Interface.NAME: "eth1",
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {"no_exist_feature": False}
        },
    }
    with pytest.raises(NmstateValueError):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for ethtool ring test",
)
def test_ethtool_ring_set_rx():
    desire_iface_state = {
        Interface.NAME: os.environ.get("TEST_REAL_NIC"),
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Ring.CONFIG_SUBTREE: {Ethtool.Ring.RX: 256}
        },
    }
    libnmstate.apply({Interface.KEY: [desire_iface_state]})

    assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})


@pytest.mark.skipif(
    nm_major_minor_version() < 1.31
    or os.environ.get("CI") == "true"
    or not is_fedora(),
    reason=(
        "Ethtool pause test need NetworkManager 1.31+ and netdevsim kernel "
        "module in Fedora 34+"
    ),
)
def test_ethtool_coalesce_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Coalesce.CONFIG_SUBTREE: {
                Ethtool.Coalesce.TX_USECS: 100,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.fixture
def veth1_with_ethtool_feature_highdma_false():
    interface_name = "veth1"
    peer_interface_name = f"{interface_name}.ep"
    iface_state = {
        Interface.NAME: interface_name,
        Interface.TYPE: Veth.TYPE,
        Interface.STATE: InterfaceState.UP,
        Veth.CONFIG_SUBTREE: {Veth.PEER: peer_interface_name},
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {
                "highdma": False,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: peer_interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ],
        },
        verify_change=False,
    )


@pytest.fixture
def veth1_with_ethtool_feature_highdma_true():
    interface_name = "veth1"
    peer_interface_name = f"{interface_name}.ep"
    iface_state = {
        Interface.NAME: interface_name,
        Interface.TYPE: Veth.TYPE,
        Interface.STATE: InterfaceState.UP,
        Veth.CONFIG_SUBTREE: {Veth.PEER: peer_interface_name},
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {
                "highdma": True,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: peer_interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ],
        },
        verify_change=False,
    )


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=("CI environment does not support ethtool via netlink yet"),
)
def test_ethtool_preserve_existing_ethtool_feature_setting(
    veth1_with_ethtool_feature_highdma_false,
):
    iface_state = veth1_with_ethtool_feature_highdma_false

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: iface_state[Interface.NAME],
                    Interface.MTU: 1400,
                }
            ]
        }
    )
    iface_state[Interface.MTU] = 1400
    assertlib.assert_state_match({Interface.KEY: [iface_state]})
