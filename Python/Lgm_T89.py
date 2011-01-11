"""
Python implementation of the LanlGeoMag T89 Magnetic field model


@author: Brian Larsen
@organization: LANL
@contact: balarsen@lanl.gov

@version: V1: 23-Dec-2010 (BAL)
"""

import ctypes
#import itertools
import datetime

import numpy as np
import spacepy.toolbox as tb
# from pylab import griddata, pcolor, pcolormesh, gca, draw

import Lgm
from Lgm_Types import LgmInt
from _Lgm import lib
import Lgm_Vector
import Lgm_CTrans
import Lgm_MagModelInfo

class Lgm_T89(object):
    """
    Python implementation of the LanlGeoMag T89 Magnetic field model

    @author: Brian Larsen
    @organization: LANL
    @contact: balarsen@lanl.gov

    @version: V1: 23-Dec-2010 (BAL)
    """
    def __init__(self, pos, time, Kp, coord_system = 'GSM', INTERNAL_MODEL='LGM_IGRF',):
        # pos must be a Lgm_Vector or list of Lgm_Vectors
        if not isinstance(pos, Lgm_Vector.Lgm_Vector) and \
            not isinstance(pos, list):
            raise(TypeError('pos must be a Lgm_Vector or list of Lgm_vectors') )
        self.position = pos
        self._Vpos = self._pos2Lgm_Vector(pos)

        # time must be a datetime
        if not isinstance(time, datetime.datetime) and \
            not isinstance(time, list):
            raise(TypeError('time must be a datetime or list of datetime') )
        self.time = time

        try:
            for val in Kp:
                if val < 0 or val > 5:
                    raise(ValueError('T89 is only defined for integer Kp from 0 to 5') )
        except TypeError:
            if Kp < 0 or Kp > 5:
                raise(ValueError('T89 is only defined for integer Kp from 0 to 5') )
        self.Kp = Kp

        if INTERNAL_MODEL not in (Lgm_MagModelInfo.LGM_CDIP,
                                  Lgm_MagModelInfo.LGM_EDIP,
                                  Lgm_MagModelInfo.LGM_IGRF) and \
            INTERNAL_MODEL not in ('LGM_CDIP',
                                  'LGM_EDIP',
                                  'LGM_IGRF'):
            raise(ValueError('INTERNAL_MODEL must be LGM_CDIP, LGM_EDIP, or LGM_IGRF') )
        if isinstance(INTERNAL_MODEL, str):
            self.INTERNAL_MODEL = Lgm_MagModelInfo.__getattribute__(INTERNAL_MODEL)
        else:
            self.INTERNAL_MODEL = INTERNAL_MODEL

        if coord_system != 'GSM':
            raise(NotImplementedError('Different coord systems are not yet ready to use') )
        self.coord_system = coord_system

        self._mmi = Lgm_MagModelInfo.Lgm_MagModelInfo()

        # either they are all one elemet or they are compatible lists no 1/2 way
        try:
            if len(self._Vpos) != len(self.Kp) or \
                len(self._Vpos) != len(self.time) or \
                len(self.time) != len(self.Kp):
                raise(ValueError('Inputs must be the same length, scalars or lists'))
        except TypeError:
            if isinstance(self._Vpos, list) and not isinstance(self.Kp, list) \
                and not isinstance(self.time, list):
                    raise(ValueError('Inputs must be the same length, scalars or lists'))

        self.B = self.calc_B()

    def calc_B(self):
        try:
            ans = []
            for v1, v2, v3 in zip(self._Vpos, self.time, self.Kp):
                date = Lgm_CTrans.dateToDateLong(v2)
                utc = Lgm_CTrans.dateToFPHours(v2)
                lib.Lgm_Set_Coord_Transforms( date, utc, self._mmi.c);
                B = Lgm_Vector.Lgm_Vector()
                self._mmi.Kp = v3
                retval = lib.Lgm_B_T89(v1, B, self._mmi)
                if retval != 1:
                    raise(RuntimeWarning('Odd return from Lgm_T89') )
                ans.append(B)
            return ans
        except TypeError:
                date = Lgm_CTrans.dateToDateLong(self.time)
                utc = Lgm_CTrans.dateToFPHours(self.time)
                lib.Lgm_Set_Coord_Transforms( date, utc, self._mmi.c);
                B = Lgm_Vector.Lgm_Vector()
                self._mmi.Kp = self.Kp
                retval = lib.Lgm_B_T89(self._Vpos, B, self._mmi)
                if retval != 1:
                    raise(RuntimeWarning('Odd return from Lgm_T89') )
                return B

    def _pos2Lgm_Vector(self, pos):
        if isinstance(pos, Lgm_Vector.Lgm_Vector):
            return pos
        if isinstance(pos, list):
            Vpos = []
            for val in pos:
                if not isinstance(val, list):
                    return Lgm_Vector.Lgm_Vector(pos[0], pos[1], pos[2])
                Vpos.append(Lgm_Vector.Lgm_Vector(val[0], val[1], val[2]))
            return Vpos
        if isinstance(pos, np.ndarray):
            raise(NotImplementedError('Only lists can be input for position now') )

def T89(pos, time, Kp, coord_system = 'GSM', INTERNAL_MODEL='LGM_IGRF',):
    """
    Easy wrapper to just return values without having to create an instance of
    Lgm_T89

    @param pos: a list of 3 element lists of positions in coord_system system
    @type pos: list
    @param time: a datetime or list of datetime objects
    @type time: (list, datetime)
    @param Kp: the Kp value for T89 (0,1,2,3,4,5)
    @type Kp: int

    @keyword coord_system: the name of the coord system to use (or Lgm number)
    @type coord_system: (str, int)
    @keyword INTERNAL_MODEL: the intermal magnetic field model to use (or Lgm number)
    @type INTERNAL_MODEL: (str, int)

    @retval: list of the x, y, z, compents of B in nT
    @rtype: list

    @author: Brian Larsen
    @organization: LANL
    @contact: balarsen@lanl.gov

    @version: V1: 11-Jan-2011 (BAL)
    """
    a = Lgm_T89(pos, time, Kp, coord_system = 'GSM',
                        INTERNAL_MODEL='LGM_IGRF')
    try:
        ret = [val.tolist() for val in a.B]
        return ret
    except TypeError:
        return a.B.tolist()
