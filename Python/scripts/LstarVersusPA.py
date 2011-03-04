import math
from ctypes import pointer, c_double, c_int
import datetime

import numpy

from spacepy import datamodel
import spacepy.toolbox as tb

from Lgm_Wrap import Lgm_Set_Coord_Transforms, SM_TO_GSM, Lgm_Convert_Coords, Lgm_Set_Lgm_B_OP77, Lgm_LstarInfo, SetLstarTolerances, Lgm_Trace, GSM_TO_SM, WGS84_A, RadPerDeg, NewTimeLstarInfo, Lstar
import Lgm_Vector
import Lgm_CTrans
import Lgm_MagEphemInfo
import DataArray
import Closed_Field
import Lgm_MagModelInfo


class Lstar_Data(datamodel.SpaceData):
    """
    Class to store data and attributes

    @author: Brian Larsen
    @organization: LANL
    @contact: balarsen@lanl.gov

    @version: V1: 03-Mar-2011 (BAL)
    """
    def __init__(self):
        self.attrs = {}
        self['position'] = {}
        #self['Bcalc'] = datamodel.dmarray([])

    def __repr__(self):
        tb.dictree(self, True)
        return ''

#def runMe():
def LstarVersusPA(pos, date, alpha = 90,
                  Kp = 2, coord_system='GSM',
                  Bfield = 'Lgm_B_OP77',
                  LsimpleThres = 10.0,
                  extended_out = False,
                  LstarQuality = 3, ):

    # setup a datamodel object to hold the answer
    ans = Lstar_Data()

    # change datetime to Lgm Datelong and UTC
    try:
        datelong = Lgm_CTrans.dateToDateLong(date)
        utc = Lgm_CTrans.dateToFPHours(date)
    except AttributeError:
        raise(TypeError("Date must be a datetime object"))
    else:
        ans['Date'] = datelong
        ans['UTC'] = utc

    # setup a magmodelinfo
    mmi = Lgm_MagModelInfo.Lgm_MagModelInfo()
    Lgm_Set_Coord_Transforms( datelong, utc, mmi.c) # dont need pointer as it is one

    # convert to **GSM**
    if coord_system == 'GSM':
        try:
            Pgsm = Lgm_Vector.Lgm_Vector(*pos)
        except TypeError:
            raise(TypeError("Position must be listlike" ) )
        ans['position']['GSM'] = datamodel.dmarray(pos, attrs={'units':'Re'})
    elif coord_system == 'SM':
        try:
            Psm = Lgm_Vector.Lgm_Vector(*pos)
        except TypeError:
            raise(TypeError("Position must be listlike" ) )
        Pgsm = Lgm_Vector.Lgm_Vector()
        Lgm_Convert_Coords( pointer(Psm), pointer(Pgsm), SM_TO_GSM, mmi.c )
        ans['position']['SM'] = datamodel.dmarray(pos, attrs={'units':'Re'})
        ans['position']['GSM'] = datamodel.dmarray(Pgsm.tolist(), attrs={'units':'Re'})
    else:
        raise(NotImplementedError("Only GSM or SM input currently supported"))

    # save Kp
    # TODO maybe add some Kp checking
    ans['Kp'] = Kp

    # pitch angles to calculate, this will be an input
    try:
        Alpha = list(alpha)
    except TypeError:
        Alpha = [alpha]

    # required setup
    MagEphemInfo = Lgm_MagEphemInfo.Lgm_MagEphemInfo(len(Alpha), 0)

    # what does 3 mean?  Have to look at the C (or docs)
    MagEphemInfo.LstarQuality = LstarQuality;

    # L* in ones place is L* in lots of places (for GPS set to False)
    MagEphemInfo.SaveShellLines = extended_out
    # TODO maybe not hardcoded, but for now its fine
    MagEphemInfo.LstarInfo.contents.VerbosityLevel = 0;
    MagEphemInfo.LstarInfo.contents.mInfo.contents.VerbosityLevel = 0;

    #MagEphemInfo->LstarInfo->mInfo->Bfield        = Lgm_B_T89;
    #MagEphemInfo->LstarInfo->mInfo->Bfield        = Lgm_B_cdip;
    #MagEphemInfo->LstarInfo->mInfo->Bfield        = Lgm_B_OP77;
    #MagEphemInfo->LstarInfo->mInfo->InternalModel = LGM_CDIP;
    # decide which field model to use, this is a keyword
    if Bfield != 'Lgm_B_OP77':
        raise(NotImplementedError("Only Bfield='Lgm_B_OP77' currently supported"))

    Lgm_Set_Lgm_B_OP77( MagEphemInfo.LstarInfo.contents.mInfo )

    # put Kp into the structure
    MagEphemInfo.LstarInfo.contents.mInfo.contents.Kp = Kp

    # Save Date, UTC to MagEphemInfo structure ** is this needed?
    MagEphemInfo.Date   = datelong
    MagEphemInfo.UTC    = utc

    # Save nAlpha, and Alpha array to MagEphemInfo structure
    MagEphemInfo.nAlpha = len(Alpha)
    MagEphemInfo.Alpha = (c_double*len(Alpha))(*Alpha)

    # Set Tolerances
    SetLstarTolerances(MagEphemInfo.LstarQuality, MagEphemInfo.LstarInfo )

    MagEphemInfo.LstarInfo.contents.mInfo.contents = mmi

    # *  Blocal at sat location.
    MagEphemInfo.P = Pgsm

    Bvec = Lgm_Vector.Lgm_Vector(0,0,0) # I like to initialize, probably not needed
    # Get B at the point in question
    MagEphemInfo.LstarInfo.contents.mInfo.contents.Bfield(pointer(Pgsm), pointer(Bvec),
                                                          MagEphemInfo.LstarInfo.contents.mInfo)
    ans['Bcalc'] = datamodel.dmarray(Bvec.tolist(), attrs={'units':'nT'})
    ans['Bcalc'].attrs['model'] = 'Lgm_B_OP77'
    ans['Bcalc'].attrs['Kp'] = Kp

    # save its magnitude in the structure
    MagEphemInfo.B = Bvec.magnitude()

    # presetup the ans[Angle] so that it can be filled correctly
    for pa in Alpha:
        ans[pa] = {}

    # check and see if the field line is closed before doing much work
    trace, northern, southern, minB, Lsimple = Closed_Field.Closed_Field(Pgsm.tolist(), date , extended_out=True)
    if trace != 'LGM_CLOSED':
        for pa in Alpha:
            ans[pa]['Lstar'] = datamodel.dmarray(numpy.nan, attrs={'info':trace})
        return ans
        # if this is not LGM_CLOSED then don't both with any pitch angle?  true?

    #  Save field-related quantities for each Pitch Angle.
    MagEphemInfo.Pmin = Lgm_Vector.Lgm_Vector(*minB)
    MagEphemInfo.Bmin = MagEphemInfo.LstarInfo.contents.mInfo.contents.Bmin
    ans[pa]['Bmin'] = datamodel.dmarray(minB, attrs={'units':'nT'})

    # LOOP OVER PITCH ANGLES
    for i, pa in enumerate(Alpha):

        PreStr = MagEphemInfo.LstarInfo.contents.PreStr
        PostStr = MagEphemInfo.LstarInfo.contents.PostStr

    # Set Pitch Angle, sin, sin^2, and Bmirror
        sa = math.sin( pa*RadPerDeg )
        sa2 = sa*sa;

        # print("{0}Computing L* for Pitch Angle: Alpha[{1}] = {2} Date: {3}   UTC: {4}   Lsimple = {5:4.3}{6}\n").format(PreStr, i, MagEphemInfo.Alpha[i], date, utc, Lsimple, PostStr )

        MagEphemInfo.LstarInfo.contents.mInfo.contents.Bm = MagEphemInfo.B/sa2
        ans[pa]['Bm'] = MagEphemInfo.LstarInfo.contents.mInfo.contents.Bm

        # I tink this is already done
        # Lgm_Set_Coord_Transforms( Date, UTC, MagEphemInfo.LstarInfo.contents.mInfo.contents.c )
        MagEphemInfo.LstarInfo.contents.PitchAngle = pa
        MagEphemInfo.Bm[i] = MagEphemInfo.LstarInfo.contents.mInfo.contents.Bm

        # Compute L*
        if Lsimple < LsimpleThres:
            Ls_vec = Lgm_Vector.Lgm_Vector(*southern)
            LS_Flag = Lstar( pointer(Ls_vec), MagEphemInfo.LstarInfo)
            if LS_Flag == -2: # mirror below souther hemisphere mirror alt
                ans[pa]['Lstar'] = datamodel.dmarray(numpy.nan, attrs={'info':'S_LOSS'})
            elif LS_Flag == -1: # mirror below souther hemisphere mirror alt
                ans[pa]['Lstar'] = datamodel.dmarray(numpy.nan, attrs={'info':'N_LOSS'})
            elif LS_Flag == 0: # valid calc
                ans[pa]['Lstar'] = datamodel.dmarray(MagEphemInfo.LstarInfo.contents.LS, attrs={'info':'N_LOSS'})

            MagEphemInfo.Lstar[i] = MagEphemInfo.LstarInfo.contents.LS

            # Save results to the MagEphemInfo structure.
            MagEphemInfo.nShellPoints[i] = MagEphemInfo.LstarInfo.contents.nPnts
            ## pull all this good extra info into numpy arrays
            ans[pa]['ShellI'] = numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.I)],
                dtype=c_double, buffer=MagEphemInfo.LstarInfo.contents.I)
            if extended_out:
                ans[pa]['ShellEllipsoidFootprint_Pn'] = \
                    numpy.ctypeslib.ndarray(len(MagEphemInfo.LstarInfo.contents.Ellipsoid_Footprint_Pn),
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.Ellipsoid_Footprint_Pn)
                ans[pa]['ShellEllipsoidFootprint_Ps'] = \
                    numpy.ctypeslib.ndarray(len(MagEphemInfo.LstarInfo.contents.Ellipsoid_Footprint_Ps),
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.Ellipsoid_Footprint_Ps)

                ans[pa]['ShellMirror_Pn'] = \
                    numpy.ctypeslib.ndarray(len(MagEphemInfo.LstarInfo.contents.Mirror_Pn),
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.Mirror_Pn)
                ans[pa]['ShellMirror_Ps'] = \
                    numpy.ctypeslib.ndarray(len(MagEphemInfo.LstarInfo.contents.Mirror_Ps),
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.Mirror_Ps)
                ans[pa]['ShellMirror_Ss'] = MagEphemInfo.LstarInfo.contents.mInfo.contents.Sm_South
                ans[pa]['ShellMirror_Sn'] = MagEphemInfo.LstarInfo.contents.mInfo.contents.Sm_North
                ans[pa]['nFieldPnts'] = \
                    numpy.ctypeslib.ndarray(len(MagEphemInfo.LstarInfo.contents.nFieldPnts),
                                            dtype=c_int,
                                            buffer=MagEphemInfo.LstarInfo.contents.nFieldPnts)

                ans[pa]['s_gsm'] = \
                    numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.s_gsm),
                                             len(MagEphemInfo.LstarInfo.contents.s_gsm[0])],
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.s_gsm)
                ans[pa]['Bmag'] = \
                    numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.Bmag),
                                             len(MagEphemInfo.LstarInfo.contents.Bmag[0])],
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.Bmag)
                ans[pa]['x_gsm'] = \
                    numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.x_gsm),
                                             len(MagEphemInfo.LstarInfo.contents.x_gsm[0])],
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.x_gsm)
                ans[pa]['y_gsm'] = \
                    numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.y_gsm),
                                             len(MagEphemInfo.LstarInfo.contents.y_gsm[0])],
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.y_gsm)
                ans[pa]['z_gsm'] = \
                    numpy.ctypeslib.ndarray([len(MagEphemInfo.LstarInfo.contents.z_gsm),
                                             len(MagEphemInfo.LstarInfo.contents.z_gsm[0])],
                                            dtype=c_double,
                                            buffer=MagEphemInfo.LstarInfo.contents.z_gsm)

    return ans

if __name__ == '__main__':
    date = datetime.datetime(2010, 10, 12)
    ans = LstarVersusPA([-4.2, 0, 0], date, alpha = 90, Kp = 2, coord_system='SM')