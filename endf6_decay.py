import re
from typing import TextIO, Tuple

import numpy as np


from collections.abc import Iterable
from math import exp, log

import numpy as np



import re
from typing import Tuple

# Dictionary to give element symbols from IUPAC names
# (and some common mispellings)
ELEMENT_SYMBOL = {
    'neutron': 'n', 'hydrogen': 'H', 'helium': 'He',
    'lithium': 'Li', 'beryllium': 'Be', 'boron': 'B',
    'carbon': 'C', 'nitrogen': 'N', 'oxygen': 'O', 'fluorine': 'F',
    'neon': 'Ne', 'sodium': 'Na', 'magnesium': 'Mg',
    'aluminium': 'Al', 'aluminum': 'Al', 'silicon': 'Si',
    'phosphorus': 'P', 'sulfur': 'S', 'sulphur': 'S',
    'chlorine': 'Cl', 'argon': 'Ar', 'potassium': 'K',
    'calcium': 'Ca', 'scandium': 'Sc', 'titanium': 'Ti',
    'vanadium': 'V', 'chromium': 'Cr', 'manganese': 'Mn',
    'iron': 'Fe', 'cobalt': 'Co', 'nickel': 'Ni', 'copper': 'Cu',
    'zinc': 'Zn', 'gallium': 'Ga', 'germanium': 'Ge',
    'arsenic': 'As', 'selenium': 'Se', 'bromine': 'Br',
    'krypton': 'Kr', 'rubidium': 'Rb', 'strontium': 'Sr',
    'yttrium': 'Y', 'zirconium': 'Zr', 'niobium': 'Nb',
    'molybdenum': 'Mo', 'technetium': 'Tc', 'ruthenium': 'Ru',
    'rhodium': 'Rh', 'palladium': 'Pd', 'silver': 'Ag',
    'cadmium': 'Cd', 'indium': 'In', 'tin': 'Sn', 'antimony': 'Sb',
    'tellurium': 'Te', 'iodine': 'I', 'xenon': 'Xe',
    'caesium': 'Cs', 'cesium': 'Cs', 'barium': 'Ba',
    'lanthanum': 'La', 'cerium': 'Ce', 'praseodymium': 'Pr',
    'neodymium': 'Nd', 'promethium': 'Pm', 'samarium': 'Sm',
    'europium': 'Eu', 'gadolinium': 'Gd', 'terbium': 'Tb',
    'dysprosium': 'Dy', 'holmium': 'Ho', 'erbium': 'Er',
    'thulium': 'Tm', 'ytterbium': 'Yb', 'lutetium': 'Lu',
    'hafnium': 'Hf', 'tantalum': 'Ta', 'tungsten': 'W',
    'wolfram': 'W', 'rhenium': 'Re', 'osmium': 'Os',
    'iridium': 'Ir', 'platinum': 'Pt', 'gold': 'Au',
    'mercury': 'Hg', 'thallium': 'Tl', 'lead': 'Pb',
    'bismuth': 'Bi', 'polonium': 'Po', 'astatine': 'At',
    'radon': 'Rn', 'francium': 'Fr', 'radium': 'Ra',
    'actinium': 'Ac', 'thorium': 'Th', 'protactinium': 'Pa',
    'uranium': 'U', 'neptunium': 'Np', 'plutonium': 'Pu',
    'americium': 'Am', 'curium': 'Cm', 'berkelium': 'Bk',
    'californium': 'Cf', 'einsteinium': 'Es', 'fermium': 'Fm',
    'mendelevium': 'Md', 'nobelium': 'No', 'lawrencium': 'Lr',
    'rutherfordium': 'Rf', 'dubnium': 'Db', 'seaborgium': 'Sg',
    'bohrium': 'Bh', 'hassium': 'Hs', 'meitnerium': 'Mt',
    'darmstadtium': 'Ds', 'roentgenium': 'Rg', 'copernicium': 'Cn',
    'nihonium': 'Nh', 'flerovium': 'Fl', 'moscovium': 'Mc',
    'livermorium': 'Lv', 'tennessine': 'Ts', 'oganesson': 'Og'
}

ATOMIC_SYMBOL = {
    0: 'n', 1: 'H', 2: 'He', 3: 'Li', 4: 'Be', 5: 'B', 6: 'C',
    7: 'N', 8: 'O', 9: 'F', 10: 'Ne', 11: 'Na', 12: 'Mg', 13: 'Al',
    14: 'Si', 15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 19: 'K',
    20: 'Ca', 21: 'Sc', 22: 'Ti', 23: 'V', 24: 'Cr', 25: 'Mn',
    26: 'Fe', 27: 'Co', 28: 'Ni', 29: 'Cu', 30: 'Zn', 31: 'Ga',
    32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr', 37: 'Rb',
    38: 'Sr', 39: 'Y', 40: 'Zr', 41: 'Nb', 42: 'Mo', 43: 'Tc',
    44: 'Ru', 45: 'Rh', 46: 'Pd', 47: 'Ag', 48: 'Cd', 49: 'In',
    50: 'Sn', 51: 'Sb', 52: 'Te', 53: 'I', 54: 'Xe', 55: 'Cs',
    56: 'Ba', 57: 'La', 58: 'Ce', 59: 'Pr', 60: 'Nd', 61: 'Pm',
    62: 'Sm', 63: 'Eu', 64: 'Gd', 65: 'Tb', 66: 'Dy', 67: 'Ho',
    68: 'Er', 69: 'Tm', 70: 'Yb', 71: 'Lu', 72: 'Hf', 73: 'Ta',
    74: 'W', 75: 'Re', 76: 'Os', 77: 'Ir', 78: 'Pt', 79: 'Au',
    80: 'Hg', 81: 'Tl', 82: 'Pb', 83: 'Bi', 84: 'Po', 85: 'At',
    86: 'Rn', 87: 'Fr', 88: 'Ra', 89: 'Ac', 90: 'Th', 91: 'Pa',
    92: 'U', 93: 'Np', 94: 'Pu', 95: 'Am', 96: 'Cm', 97: 'Bk',
    98: 'Cf', 99: 'Es', 100: 'Fm', 101: 'Md', 102: 'No',
    103: 'Lr', 104: 'Rf', 105: 'Db', 106: 'Sg', 107: 'Bh',
    108: 'Hs', 109: 'Mt', 110: 'Ds', 111: 'Rg', 112: 'Cn',
    113: 'Nh', 114: 'Fl', 115: 'Mc', 116: 'Lv', 117: 'Ts',
    118: 'Og'
}
ATOMIC_NUMBER = {value: key for key, value in ATOMIC_SYMBOL.items()}

# Boltzmann constant in [eV/K]
K_BOLTZMANN = 8.617333262e-5

EV_PER_MEV = 1.0e6

# Regex for GNDS nuclide names (used in zam function)
_GNDS_NAME_RE = re.compile(r'([A-Zn][a-z]*)(\d+)((?:_[em]\d+)?)')


def gnds_name(Z: int, A: int, m: int = 0) -> str:
    """Return nuclide name using GNDS convention

    Parameters
    ----------
    Z
        Atomic number
    A
        Mass number
    m
        Metastable state

    Returns
    -------
    Nuclide name in GNDS convention, e.g., 'Am242_m1'

    """
    if m > 0:
        return f'{ATOMIC_SYMBOL[Z]}{A}_m{m}'
    return f'{ATOMIC_SYMBOL[Z]}{A}'


def zam(name: str) -> Tuple[int, int, int]:
    """Return tuple of (atomic number, mass number, metastable state)

    Parameters
    ----------
    name
        Name of nuclide using GNDS convention, e.g., 'Am242_m1'

    Returns
    -------
    Atomic number, mass number, and metastable state

    """
    try:
        symbol, A, state = _GNDS_NAME_RE.match(name).groups()
    except AttributeError:
        raise ValueError(f"'{name}' does not appear to be a nuclide name in "
                         "GNDS format")

    if symbol not in ATOMIC_NUMBER:
        raise ValueError(f"'{symbol}' is not a recognized element symbol")

    metastable = int(state[2:]) if state else 0
    return (ATOMIC_NUMBER[symbol], int(A), metastable)


def temperature_str(T: float) -> str:
    """Return temperature as a string

    Parameters
    ----------
    T
        Temperature in [K]

    Returns
    -------
    String representation of temperature, e.g., '294K'

    """
    return "{}K".format(int(round(T)))


class Tabulated1D:
    """A one-dimensional tabulated function.

    This class mirrors the TAB1 type from the ENDF-6 format. A tabulated
    function is specified by tabulated (x,y) pairs along with interpolation
    rules that determine the values between tabulated pairs.

    Once an object has been created, it can be used as though it were an actual
    function, e.g.:

    >>> f = Tabulated1D([0, 10], [4, 5])
    >>> [f(xi) for xi in numpy.linspace(0, 10, 5)]
    [4.0, 4.25, 4.5, 4.75, 5.0]

    Parameters
    ----------
    x : Iterable of float
        Independent variable
    y : Iterable of float
        Dependent variable
    breakpoints : Iterable of int
        Breakpoints for interpolation regions
    interpolation : Iterable of int
        Interpolation scheme identification number, e.g., 3 means y is linear in
        ln(x).

    Attributes
    ----------
    x : Iterable of float
        Independent variable
    y : Iterable of float
        Dependent variable
    breakpoints : Iterable of int
        Breakpoints for interpolation regions
    interpolation : Iterable of int
        Interpolation scheme identification number, e.g., 3 means y is linear in
        ln(x).
    n_regions : int
        Number of interpolation regions
    n_pairs : int
        Number of tabulated (x,y) pairs

    """

    def __init__(self, x, y, breakpoints=None, interpolation=None):
        if breakpoints is None or interpolation is None:
            # Single linear-linear interpolation region by default
            self.breakpoints = np.array([len(x)])
            self.interpolation = np.array([2])
        else:
            self.breakpoints = np.asarray(breakpoints, dtype=int)
            self.interpolation = np.asarray(interpolation, dtype=int)

        self.x = np.asarray(x)
        self.y = np.asarray(y)

    def __repr__(self):
        return f"<Tabulated1D: {self.x.size} points, {self.breakpoints.size} regions>"

    def __call__(self, x):
        # Check if input is scalar
        if not isinstance(x, Iterable):
            return self._interpolate_scalar(x)

        x = np.array(x)

        # Create output array
        y = np.zeros_like(x)

        # Get indices for interpolation
        idx = np.searchsorted(self.x, x, side='right') - 1

        # Loop over interpolation regions
        for k in range(len(self.breakpoints)):
            # Get indices for the begining and ending of this region
            i_begin = self.breakpoints[k-1] - 1 if k > 0 else 0
            i_end = self.breakpoints[k] - 1

            # Figure out which idx values lie within this region
            contained = (idx >= i_begin) & (idx < i_end)

            xk = x[contained]                 # x values in this region
            xi = self.x[idx[contained]]       # low edge of corresponding bins
            xi1 = self.x[idx[contained] + 1]  # high edge of corresponding bins
            yi = self.y[idx[contained]]
            yi1 = self.y[idx[contained] + 1]

            if self.interpolation[k] == 1:
                # Histogram
                y[contained] = yi

            elif self.interpolation[k] == 2:
                # Linear-linear
                y[contained] = yi + (xk - xi)/(xi1 - xi)*(yi1 - yi)

            elif self.interpolation[k] == 3:
                # Linear-log
                y[contained] = yi + np.log(xk/xi)/np.log(xi1/xi)*(yi1 - yi)

            elif self.interpolation[k] == 4:
                # Log-linear
                y[contained] = yi*np.exp((xk - xi)/(xi1 - xi)*np.log(yi1/yi))

            elif self.interpolation[k] == 5:
                # Log-log
                y[contained] = (yi*np.exp(np.log(xk/xi)/np.log(xi1/xi)
                                *np.log(yi1/yi)))

        # In some cases, x values might be outside the tabulated region due only
        # to precision, so we check if they're close and set them equal if so.
        y[np.isclose(x, self.x[0], atol=1e-14)] = self.y[0]
        y[np.isclose(x, self.x[-1], atol=1e-14)] = self.y[-1]

        return y

    def _interpolate_scalar(self, x):
        if x <= self._x[0]:
            return self._y[0]
        elif x >= self._x[-1]:
            return self._y[-1]

        # Get the index for interpolation
        idx = np.searchsorted(self._x, x, side='right') - 1

        # Loop over interpolation regions
        for b, p in zip(self.breakpoints, self.interpolation):
            if idx < b - 1:
                break

        xi = self._x[idx]       # low edge of the corresponding bin
        xi1 = self._x[idx + 1]  # high edge of the corresponding bin
        yi = self._y[idx]
        yi1 = self._y[idx + 1]

        if p == 1:
            # Histogram
            return yi

        elif p == 2:
            # Linear-linear
            return yi + (x - xi)/(xi1 - xi)*(yi1 - yi)

        elif p == 3:
            # Linear-log
            return yi + log(x/xi)/log(xi1/xi)*(yi1 - yi)

        elif p == 4:
            # Log-linear
            return yi*exp((x - xi)/(xi1 - xi)*log(yi1/yi))

        elif p == 5:
            # Log-log
            return yi*exp(log(x/xi)/log(xi1/xi)*log(yi1/yi))

    def __len__(self):
        return len(self.x)

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def breakpoints(self):
        return self._breakpoints

    @property
    def interpolation(self):
        return self._interpolation

    @property
    def n_pairs(self):
        return len(self.x)

    @property
    def n_regions(self):
        return len(self.breakpoints)

    @x.setter
    def x(self, x):
        self._x = x

    @y.setter
    def y(self, y):
        self._y = y

    @breakpoints.setter
    def breakpoints(self, breakpoints):
        self._breakpoints = breakpoints

    @interpolation.setter
    def interpolation(self, interpolation):
        self._interpolation = interpolation

    def integral(self):
        """Integral of the tabulated function over its tabulated range.

        Returns
        -------
        numpy.ndarray
            Array of same length as the tabulated data that represents partial
            integrals from the bottom of the range to each tabulated point.

        """

        # Create output array
        partial_sum = np.zeros(len(self.x) - 1)

        i_low = 0
        for k in range(len(self.breakpoints)):
            # Determine which x values are within this interpolation range
            i_high = self.breakpoints[k] - 1

            # Get x values and bounding (x,y) pairs
            x0 = self.x[i_low:i_high]
            x1 = self.x[i_low + 1:i_high + 1]
            y0 = self.y[i_low:i_high]
            y1 = self.y[i_low + 1:i_high + 1]

            if self.interpolation[k] == 1:
                # Histogram
                partial_sum[i_low:i_high] = y0*(x1 - x0)

            elif self.interpolation[k] == 2:
                # Linear-linear
                m = (y1 - y0)/(x1 - x0)
                partial_sum[i_low:i_high] = (y0 - m*x0)*(x1 - x0) + \
                                            m*(x1**2 - x0**2)/2

            elif self.interpolation[k] == 3:
                # Linear-log
                logx = np.log(x1/x0)
                m = (y1 - y0)/logx
                partial_sum[i_low:i_high] = y0 + m*(x1*(logx - 1) + x0)

            elif self.interpolation[k] == 4:
                # Log-linear
                m = np.log(y1/y0)/(x1 - x0)
                partial_sum[i_low:i_high] = y0/m*(np.exp(m*(x1 - x0)) - 1)

            elif self.interpolation[k] == 5:
                # Log-log
                m = np.log(y1/y0)/np.log(x1/x0)
                partial_sum[i_low:i_high] = y0/((m + 1)*x0**m)*(
                    x1**(m + 1) - x0**(m + 1))

            i_low = i_high

        return np.concatenate(([0.], np.cumsum(partial_sum)))

    @classmethod
    def from_ace(cls, ace, idx=0, convert_units=True):
        """Create a Tabulated1D object from an ACE table.

        Parameters
        ----------
        ace : openmc.data.ace.Table
            An ACE table
        idx : int
            Offset to read from in XSS array (default of zero)
        convert_units : bool
            If the abscissa represents energy, indicate whether to convert MeV
            to eV.

        Returns
        -------
        openmc.data.Tabulated1D
            Tabulated data object

        """

        # Get number of regions and pairs
        n_regions = int(ace.xss[idx])
        n_pairs = int(ace.xss[idx + 1 + 2*n_regions])

        # Get interpolation information
        idx += 1
        if n_regions > 0:
            breakpoints = ace.xss[idx:idx + n_regions].astype(int)
            interpolation = ace.xss[idx + n_regions:idx + 2*n_regions].astype(int)
        else:
            # 0 regions implies linear-linear interpolation by default
            breakpoints = np.array([n_pairs])
            interpolation = np.array([2])

        # Get (x,y) pairs
        idx += 2*n_regions + 1
        x = ace.xss[idx:idx + n_pairs].copy()
        y = ace.xss[idx + n_pairs:idx + 2*n_pairs].copy()

        if convert_units:
            x *= EV_PER_MEV

        return Tabulated1D(x, y, breakpoints, interpolation)


class Tabulated2D:
    """Metadata for a two-dimensional function.

    This is a dummy class that is not really used other than to store the
    interpolation information for a two-dimensional function. Once we refactor
    to adopt GNDS-like data containers, this will probably be removed or
    extended.

    Parameters
    ----------
    breakpoints : Iterable of int
        Breakpoints for interpolation regions
    interpolation : Iterable of int
        Interpolation scheme identification number, e.g., 3 means y is linear in
        ln(x).

    """
    def __init__(self, breakpoints, interpolation):
        self.breakpoints = breakpoints
        self.interpolation = interpolation

ENDF_FLOAT_RE = re.compile(r'([\s\-\+]?\d*\.\d+)([\+\-]) ?(\d+)')


def py_float_endf(s: str) -> float:
    """Convert string of floating point number in ENDF to float.

    The ENDF-6 format uses an 'e-less' floating point number format,
    e.g. -1.23481+10. Trying to convert using the float built-in won't work
    because of the lack of an 'e'. This function allows such strings to be
    converted while still allowing numbers that are not in exponential notation
    to be converted as well.

    Parameters
    ----------
    s : str
        Floating-point number from an ENDF file

    Returns
    -------
    float
        The number

    """
    return float(ENDF_FLOAT_RE.sub(r'\1e\2\3', s))


def int_endf(s: str) -> int:
    """Convert string of integer number in ENDF to int.

    The ENDF-6 format technically allows integers to be represented by a field
    of all blanks. This function acts like int(s) except when s is a string of
    all whitespace, in which case zero is returned.

    Parameters
    ----------
    s : str
        Integer or spaces

    Returns
    -------
    integer
        The number or 0
    """
    return 0 if s.isspace() else int(s)


def get_text_record(file_obj) -> str:
    """Return data from a TEXT record in an ENDF-6 file.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from

    Returns
    -------
    str
        Text within the TEXT record

    """
    return file_obj.readline()[:66]


def get_cont_record(file_obj, skip_c=False):
    """Return data from a CONT record in an ENDF-6 file.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from
    skip_c : bool
        Determine whether to skip the first two quantities (C1, C2) of the CONT
        record.

    Returns
    -------
    tuple
        The six items within the CONT record

    """
    line = file_obj.readline()
    if skip_c:
        C1 = None
        C2 = None
    else:
        C1 = py_float_endf(line[:11])
        C2 = py_float_endf(line[11:22])
    L1 = int_endf(line[22:33])
    L2 = int_endf(line[33:44])
    N1 = int_endf(line[44:55])
    N2 = int_endf(line[55:66])
    return (C1, C2, L1, L2, N1, N2)


def get_head_record(file_obj):
    """Return data from a HEAD record in an ENDF-6 file.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from

    Returns
    -------
    tuple
        The six items within the HEAD record

    """
    line = file_obj.readline()
    ZA = int(py_float_endf(line[:11]))
    AWR = py_float_endf(line[11:22])
    L1 = int_endf(line[22:33])
    L2 = int_endf(line[33:44])
    N1 = int_endf(line[44:55])
    N2 = int_endf(line[55:66])
    return (ZA, AWR, L1, L2, N1, N2)


def get_list_record(file_obj: TextIO) -> Tuple[list, np.ndarray]:
    """Return data from a LIST record in an ENDF-6 file.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from

    Returns
    -------
    list
        The six items within the header
    numpy.ndarray
        The values within the list

    """
    # determine how many items are in list
    items = get_cont_record(file_obj)
    NPL = items[4]

    # read items
    b = np.empty(NPL)
    for i in range((NPL - 1)//6 + 1):
        line = file_obj.readline()
        n = min(6, NPL - 6*i)
        for j in range(n):
            b[6*i + j] = py_float_endf(line[11*j:11*(j + 1)])

    return (items, b)


def get_tab1_record(file_obj):
    """Return data from a TAB1 record in an ENDF-6 file.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from

    Returns
    -------
    list
        The six items within the header
    openmc.data.Tabulated1D
        The tabulated function

    """
    # Determine how many interpolation regions and total points there are
    line = file_obj.readline()
    C1 = py_float_endf(line[:11])
    C2 = py_float_endf(line[11:22])
    L1 = int_endf(line[22:33])
    L2 = int_endf(line[33:44])
    n_regions = int_endf(line[44:55])
    n_pairs = int_endf(line[55:66])
    params = [C1, C2, L1, L2]

    # Read the interpolation region data, namely NBT and INT
    breakpoints = np.zeros(n_regions, dtype=int)
    interpolation = np.zeros(n_regions, dtype=int)
    m = 0
    for i in range((n_regions - 1)//3 + 1):
        line = file_obj.readline()
        to_read = min(3, n_regions - m)
        for j in range(to_read):
            breakpoints[m] = int_endf(line[0:11])
            interpolation[m] = int_endf(line[11:22])
            line = line[22:]
            m += 1

    # Read tabulated pairs x(n) and y(n)
    x = np.zeros(n_pairs)
    y = np.zeros(n_pairs)
    m = 0
    for i in range((n_pairs - 1)//3 + 1):
        line = file_obj.readline()
        to_read = min(3, n_pairs - m)
        for j in range(to_read):
            x[m] = py_float_endf(line[:11])
            y[m] = py_float_endf(line[11:22])
            line = line[22:]
            m += 1

    return params, Tabulated1D(x, y, breakpoints, interpolation)


def get_tab2_record(file_obj):
    # Determine how many interpolation regions and total points there are
    params = get_cont_record(file_obj)
    n_regions = params[4]

    # Read the interpolation region data, namely NBT and INT
    breakpoints = np.zeros(n_regions, dtype=int)
    interpolation = np.zeros(n_regions, dtype=int)
    m = 0
    for _ in range((n_regions - 1)//3 + 1):
        line = file_obj.readline()
        to_read = min(3, n_regions - m)
        for _ in range(to_read):
            breakpoints[m] = int(line[0:11])
            interpolation[m] = int(line[11:22])
            line = line[22:]
            m += 1

    return params, Tabulated2D(breakpoints, interpolation)


def get_intg_record(file_obj):
    """
    Return data from an INTG record in an ENDF-6 file. Used to store the
    covariance matrix in a compact format.

    Parameters
    ----------
    file_obj : file-like object
        ENDF-6 file to read from

    Returns
    -------
    numpy.ndarray
        The correlation matrix described in the INTG record
    """
    # determine how many items are in list and NDIGIT
    items = get_cont_record(file_obj)
    ndigit = items[2]
    npar = items[3]    # Number of parameters
    nlines = items[4]  # Lines to read
    NROW_RULES = {2: 18, 3: 12, 4: 11, 5: 9, 6: 8}
    nrow = NROW_RULES[ndigit]

    # read lines and build correlation matrix
    corr = np.identity(npar)
    for i in range(nlines):
        line = file_obj.readline()
        ii = int_endf(line[:5]) - 1  # -1 to account for 0 indexing
        jj = int_endf(line[5:10]) - 1
        factor = 10**ndigit
        for j in range(nrow):
            if jj+j >= ii:
                break
            element = int_endf(line[11+(ndigit+1)*j:11+(ndigit+1)*(j+1)])
            if element > 0:
                corr[ii, jj] = (element+0.5)/factor
            elif element < 0:
                corr[ii, jj] = (element-0.5)/factor

    # Symmetrize the correlation matrix
    corr = corr + corr.T - np.diag(corr.diagonal())
    return corr

def parse_mf8_mt457(file_obj: TextIO) -> dict:
    """Parse radioactive decay data from MF=8, MT=457

    Parameters
    ----------
    file_obj
        File-like object to read from

    Returns
    -------
    dict
        Radioactive decay data

    """
    # Get head record
    ZA, AWR, LIS, LISO, NST, NSP = get_head_record(file_obj)
    data = {'ZA': ZA, 'AWR': AWR, 'LIS': LIS, 'LISO': LISO, 'NST': NST, 'NSP': NSP}

    # Check if nuclide is stable
    if NST == 1:
        get_list_record(file_obj)
        (SPI, PAR, *_), values = get_list_record(file_obj)
        data['SPI'] = SPI
        data['PAR'] = PAR
        return data

    # Half-life and decay energies
    items, values = get_list_record(file_obj)
    data['T1/2'] = (items[0], items[1])
    data['NC'] = NC = items[4]//2
    data['Ex'] = list(zip(values[::2], values[1::2]))

    items, values = get_list_record(file_obj)
    data['SPI'], data['PAR'], *_ = items

    # Decay mode information
    data['NDK'] = NDK = items[5]  # Number of decay modes
    data['modes'] = []
    for i in range(NDK):
        RTYP = values[6*i]
        RFS = values[6*i + 1]
        Q = tuple(values[6*i + 2:6*i + 4])
        BR = tuple(values[6*i + 4:6*(i + 1)])
        mode = {'RTYP': RTYP, 'RFS': RFS, 'Q': Q, 'BR': BR}
        data['modes'].append(mode)

    # Read spectra
    data['spectra'] = []
    for i in range(NSP):
        items, values = get_list_record(file_obj)
        _, STYP, LCON, LCOV, _, NER = items
        spectrum = {'STYP': STYP, 'LCON': LCON, 'LCOV': LCOV, 'NER': NER}

        # Decay radiation type
        spectrum['FD'] = tuple(values[0:2])
        spectrum['ER_AV'] = tuple(values[2:4])
        spectrum['FC'] = tuple(values[4:6])

        if LCON != 1:
            # Information about discrete spectrum
            spectrum['discrete'] = []
            for j in range(NER):
                items, values = get_list_record(file_obj)
                discrete = {}
                discrete['ER'] = tuple(items[0:2])
                discrete['RTYP'] = values[0]
                discrete['TYPE'] = values[1]
                if STYP == 0:
                    discrete['RI'] = tuple(values[2:4])
                    discrete['RIS'] = tuple(values[4:6])
                    discrete['RICC'] = tuple(values[6:8])
                    discrete['RICK'] = tuple(values[8:10])
                    discrete['RICL'] = tuple(values[10:12])
                spectrum['discrete'].append(discrete)

        if LCON != 0:
            # Read continuous spectrum
            params, RP = get_tab1_record(file_obj)
            spectrum['continuous'] = {'RTYP': params[0], 'RP': RP}

        # Read continuous covariance (Ek, Fk) table
        if LCOV not in (0, 2) and LCON != 0:
            items, values = get_list_record(file_obj)
            covar_continuous = {'LB': items[3]}
            covar_continuous['Ek'] = np.array(values[::2])
            covar_continuous['Fk'] = np.array(values[1::2])
            spectrum['continuous_covariance'] = covar_continuous

        if LCOV not in (0, 1):
            (_, _, LS, LB, NE, NERP), values = get_list_record(file_obj)
            covar_discrete = {'LS': LS, 'LB': LB, 'NE': NE, 'NERP': NERP}
            covar_discrete['Ek'] = np.array(values[:NERP])
            covar_discrete['Fkk'] = np.array(values[NERP:])
            # TODO: Reorder and shape Fkk based on the packing order described
            # in section 8.4 of the ENDF manual
            spectrum['discrete_covariance'] = covar_discrete

        # Add spectrum to list
        data['spectra'].append(spectrum)

    return data
