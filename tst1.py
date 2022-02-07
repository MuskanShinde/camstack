'''
    KALAO NuVu Camera driver
'''
import os,sys
import datetime, time
import json
from enum import Enum
from typing import Union

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")

from camstack.core.edtinterface import EdtInterfaceSerial
from camstack.core.utilities import CameraMode
from camstack.cams.edt_base import EDTCamera

class NUVU(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'GetReadoutMode', 'SetExposureTime','GetReadoutTime', 'GetExposureTime', 'SetExposureTime', 'SetCCDTemperature',
        'GetCCDTemperature', 'GetEMCalibratedGain', 'SetEMCalibratedGain', 'GetEMRawGain', 'SetEMRawGain',
        'GetAnalogicGain', 'SetAnalogicGain', 'FULL'] + \
        EDTCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'full'

    MODES = {
        # FULL 128 x 128
        FULL: CameraMode(x0=0, x1=127, y0=0, y1=127),
        0: CameraMode(x0=0, x1=127, y0=0, y1=127),
    }

    KEYWORDS = {}
    KEYWORDS.update(EDTCamera.KEYWORDS)

    EDTTAKE_UNSIGNED = False

    class _ShutterExternal(Enum):
        NO = 0
        YES = 1

    class _Polarity(Enum):
        NEG = -1
        POS = 1

    class _ShutterMode(Enum):
        OPEN = 2
        CLOSE = -2
        AUTO= 0

    class _TriggerMode(Enum):
        EXT_H2L_EXP = -2
        EXT_H2L = -1
        INT = 0
        EXT_L2H = 1
        EXT_L2H_EXP = 2

    cfgdict = {}
    edt_iface = None
    RO_MODES=[]

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 0,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        debug=0
        basefile = os.environ['HOME'] + '/src/camstack/config/nuvu_kalao.cfg'

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name, mode_id, unit, channel,
                           basefile, taker_cset_prio=taker_cset_prio, dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        success = self._update_nuvu_config()
        if not success:
            return None

        success = self.UpdateReadoutModesList()
        if not success:
            return None

        success = self.SetReadoutModeStr('EM_20MHz_10MHz')
        if not success:
            return None

        self.camera_shm.update_keyword('DETECTOR', "NUVU - %s"%(self.cfgdict['CCDPartNumber']))

        self.SetCCDTemperature(-60.0)

        if debug:
            print(self.cfgdict)

    def __old_init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 0,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        debug=0

        self.edt_iface = EdtInterfaceSerial(unit, channel)

        success = self._update_nuvu_config()
        if not success:
            return None

        success = self._update_romodes_list()
        if not success:
            return None

        romode = 'EM_20MHz_10MHz'
        success = self.SetReadoutModeStr('EM_20MHz_10MHz')
        if not success:
            return None

        romode=4
        res = self.edt_iface.send_command("ld 4\n",base_timeout=400)
        (success,resdict) = self._get_nuvu_response(res, verbose=0)
        if success:
            self.cfgdict.update(resdict)
        else:
            return None

        self.camera_shm.update_keyword('DETECTOR', "NUVU - %s"%(self.cfgdict['CCDPartNumber']))

        if debug:
            print(self.cfgdict)

    def _get_nuvu_response(self, response, verbose=0):
        """ convert nuvu response into a key/values dictionary """
        rlines = response.splitlines()
        if not 'OK' in rlines[-2]: return(False,{})
        try:
            return(True,int(rlines[0]))
        except ValueError:
            try:
                return(True,float(rlines[0]))
            except ValueError:
                #pass
                if 3 == len(rlines) and not ':' in rlines[0]: return(True,rlines[0].split())
        rlines=list(filter(lambda x:':' in x, rlines))
        rlist=[x.split(":") for x in rlines]
        rdict = dict(zip(list(map(lambda x: x[0], rlist)), list(map(lambda x: x[1], rlist))))
        if verbose:
            #print(rdict.keys())
            #print(rdict.values())
            print(rdict)
        return(True, rdict)

    def send_command(self, cmd, timeout: float = 100., verbose=0):
        # Just a little bit of parsing to handle the NUVU answer
        if verbose:
            print(cmd)
        resp = EDTCamera.send_command(self, "{command}\n".format(command=cmd), base_timeout=timeout)
        (success,resdict) = self._get_nuvu_response(resp)
        return(success,resdict)

    def _update_nuvu_config(self):
        (success,resdict) = self.send_command("ld 0")
        if success:
            self.cfgdict.update(resdict)
        return success

    def SetReadoutModeStr(self, romode):
        if not romode in self.RO_MODES:
            return False
        (success,resdict) = self.send_command("ld %d"%(self.RO_MODES.index(romode)), timeout=400.)
        if success:
            self.camera_shm.update_keyword('DETMODE', romode)
            self.cfgdict.update(resdict)
        return success

    def SetReadoutModeInt(self, romode: int):
        if 0 > i and i > len(self.RO_MODES):
            return False
        (success,resdict) = self.send_command("ld %d"%(romode), timeout=400.)
        if success:
            self.camera_shm.update_keyword('DETMODE', self.RO_MODES['romode'])
            self.cfgdict.update(resdict)
        return success

    def _update_romodes_list(self):
        (success,resdict) = self.send_command("ls")
        if success:
            for i in range(len(resdict)):  self.RO_MODES.append(resdict[str(i)].split()[0])
        return success

    def GetReadoutMode(self):
        (success,answer) = self.send_command("ld")
        if success:
            return(int(answer),self.RO_MODES[int(answer)])
        return 'failed'

    def GetReadoutTime(self):
        (success,answer) = self.send_command("rsrt")
        if success:
            return float(answer)
        return 'failed'

    def GetExposureTime(self):
        (success,answer) = self.send_command("se")
        if success:
            texp = float(answer)
            self.camera_shm.update_keyword('EXPTIME', texp)
            self.camera_shm.update_keyword('FRATE', 1. /texp)
            return float(answer)
        return 'failed'

    def SetExposureTime(self, texp: float):
        if texp > 1172812000.0:
            return self.GetExposureTime()
        (success,answer) = self.send_command(f'se {texp}')
        if success:
            return float(answer)
        return 'failed'

    def GetWaitingTime(self):
        (success,answer) = self.send_command("sw")
        if success:
            return float(answer)
        return 'failed'

    def SetWaitingTime(self, twait: float):
        if twait > 1172812000.0:
            return self.GetWaitingTime()
        (success,answer) = self.send_command(f'sw {twait}')
        if success:
            return float(answer)
        return 'failed'

    def GetExternalShutterMode(self):
        (success,answer) = self.send_command("sesm")
        if success:
            return answer
        return 'failed'

    def SetExternalShutterMode(self, smode: _ShutterMode):
        if not smode in [item.value for item in self._ShutterMode]:
            return self.GetExternalShutterMode()
        (success,answer) = self.send_command(f'sesm {smode}')
        if success:
            return answer
        return 'failed'

    def GetExternalShutterDelay(self):
        (success,answer) = self.send_command("ssd")
        if success:
            return float(answer)
        return 'failed'

    def SetExternalShutterDelay(self, sdelay: float):
        if sdelay > 1172812000.0:
            return self.GetExternalShutterDelay()
        (success,answer) = self.send_command(f'ssd {sdelay}')
        if success:
            return float(answer)
        return 'failed'

    def GetShutterMode(self):
        (success,answer) = self.send_command("ssm")
        if success:
            return answer
        return 'failed'

    def SetShutterMode(self, smode: _ShutterMode):
        if not smode in [item.value for item in self._ShutterMode]:
            return self.GetShutterMode()
        (success,answer) = self.send_command(f'ssm {smode}')
        if success:
            return answer
        return 'failed'

    def GetShutterExternal(self):
        (success,answer) = self.send_command("sesp")
        if success:
            return answer
        return 'failed'

    def SetShutterExternal(self, sext: _ShutterExternal):
        if not sext in [item.value for item in self._ShutterExternal]:
            return self.GetShutterExternal()
        (success,answer) = self.send_command(f'sesp {sext}')
        if success:
            return answer
        return 'failed'

    def GetShutterPolarity(self):
        (success,answer) = self.send_command("ssp")
        if success:
            return answer
        return 'failed'

    def SetShutterPolarity(self, spol: _Polarity):
        if not spol in [item.value for item in self._Polarity]:
            return self.GetShutterPolarity()
        (success,answer) = self.send_command(f'ssp {spol}')
        if success:
            return answer
        return 'failed'

    def GetFirePolarity(self):
        (success,answer) = self.send_command("sfp")
        if success:
            return answer
        return 'failed'

    def SetFirePolarity(self, fpol: _Polarity):
        if not fpol in [item.value for item in self._Polarity]:
            return self.GetFirePolarity()
        (success,answer) = self.send_command(f'sfp {fpol}')
        if success:
            return answer
        return 'failed'

    def GetTriggerMode(self):
        (success,answer) = self.send_command("stm")
        if success:
            self.camera_shm.update_keyword('EXTTRIG', str(answer))
            return answer
        return 'failed'

    def SetTriggerMode(self, tmode: _TriggerMode, nimages: int):
        if not tmode in [item.value for item in self._TriggerMode]:
            return self.GetTriggerMode()
        (success,answer) = self.send_command(f'stm {tmode} {nimages}')
        if success:
            return answer
        return 'failed'

    def  GetCtrlTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetTempCtrlCmd']))
        if success:
            return(float(answer['0']))
        return 'failed'

    def  GetCCDTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetTempCCDCmd']))
        if success:
            temp = float(answer['1'])
            self.camera_shm.update_keyword('DET-TMP', temp + 273.15)
            return(temp)
        return 'failed'

    def GetSetCCDTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetSetTempCCDCmd']))
        if success:
            return float(answer['1'])
        return 'failed'

    def SetCCDTemperature(self, value: float):
        minv = float(self.cfgdict['TempCCDRange'].split(',')[0])
        maxv = float(self.cfgdict['TempCCDRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetCCDTemperature())
        cmdstring=self.cfgdict['SetTempCCDCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return float(answer['1'])
        return 'failed'

    def GetEMRawGain(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['EMGetRawGainCmd']))
        if success:
            return(int(answer['4'].split()[0]),answer['4'].split(' ',2)[2])

    def GetAnalogicGain(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetGainCmd']))
        if success:
            gain = int(answer['Gain 1'])
            self.camera_shm.update_keyword('GAIN', gain)
            return gain

    def GetAnalogicOffset(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetOffsetCmd']))
        if success:
            return int(answer['CDS offset'])

    def SetAnalogicGain(self, value: int):
        if not str(value) in self.cfgdict['AnalogicGainRange']:
            return(self.GetAnalogicGainCmd())
        cmdstring=self.cfgdict['AnalogicSetGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['Gain 1'])

    def SetAnalogicOffset(self, value: int):
        minv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[0])
        maxv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetAnalogicOffset())
        cmdstring=self.cfgdict['AnalogicSetOffsetCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['CDS offset'])

    def SetEMRawGain(self, value: int, verbose = 1):
        minv = int(self.cfgdict['EMRawGainRange'].split(',')[0])
        maxv = int(self.cfgdict['EMRawGainRange'].split(',')[1])
        maxv = 200
        if verbose:
            print(f'{minv} <= {value} <= {maxv}')
        if maxv < value and value < minv:
            return(self.GetEMRawGain())
        cmdstring=self.cfgdict['EMSetRawGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return(int(answer['4'].split()[0]),answer['4'].split(' ',2)[2])

    def GetEMCalibratedGain(self):
        (success,answer) = self.send_command("seg")
        if success:
            return float(answer['emgain'].split(',')[0])

    def SetEMCalibratedGain(self, emcgain: float):
        minv = 1.0
        maxv = 5000.0
        ccdtemp = self.GetCCDTemperature()
        mint = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[0])
        maxt = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[1])
        if maxt < ccdtemp and ccdtemp < mint:
            return(self.GetEMCalibratedGain())
        if maxv < emcgain and emcgain < minv:
            return(self.GetEMCalibratedGain())
        (success,answer) = self.send_command(f'seg {emcgain}\n')
        if success:
            return float(answer['emgain'])

    def mytemptests(self):
        print(self.SetCCDTemperature(-59.5))
        print(self.GetCtrlTemperature())
        print(self.GetSetCCDTemperature())
        print(self.GetCCDTemperature())

    def mydivtests(self):
        print(self.GetReadoutMode())
        print(self.GetReadoutTime())
        print(self.GetExposureTime())
        print(self.SetExposureTime(0))
        print(self.SetShutterMode(3.4))
        print(self.GetShutterMode())

    def mytrigtests(self):
        print(self.GetTriggerMode())
        print(self.SetTriggerMode(2,1))
        print(self.GetTriggerMode())
        print(self.SetTriggerMode(0,1))
        print(self.GetTriggerMode())

    def mygaintests(self):
        print(self.GetEMRawGain())
        print(self.SetEMRawGain(0))
        print(self.GetEMRawGain())
        print(self.GetAnalogicGain())
        print(self.SetAnalogicGain(1))
        print(self.GetAnalogicGain())
        print(self.GetAnalogicOffset())
        print(self.SetAnalogicOffset(-1000))
        print(self.GetAnalogicOffset())
        print(self.GetEMCalibratedGain())


# Quick shorthand for testing

if __name__ == "__main__":
    kalao = NUVU(name='ḱalao', stream_name='nuvucam0', unit=0, channel=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(kalao, globals())
    #kalao.mytemptests()
    #kalao.mydivtests()
    #kalao.mytrigtests()
    #kalao.mygaintests()




