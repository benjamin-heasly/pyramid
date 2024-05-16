from typing import Any
from math import factorial

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pyramid.trials.trials import Trial, TrialEnhancer


# Utility from: https://scipy.github.io/old-wiki/pages/Cookbook/SavitzkyGolay
def savitzky_golay(y, window_size, order, deriv=0, rate=1):
    """Smooth (and optionally differentiate) data with a Savitzky-Golay filter.

    The Savitzky-Golay filter removes high frequency noise from data.
    It has the advantage of preserving the original shape and
    features of the signal better than other types of filtering
    approaches, such as moving averages techniques.

    Parameters
    ----------
    y : array_like, shape (N,)
        the values of the time history of the signal.
    window_size : int
        the length of the window. Must be an odd integer number.
    order : int
        the order of the polynomial used in the filtering.
        Must be less then `window_size` - 1.
    deriv: int
        the order of the derivative to compute (default = 0 means only smoothing)

    Returns
    -------
    ys : ndarray, shape (N)
        the smoothed signal (or it's n-th derivative).

    Notes
    -----
    The Savitzky-Golay is a type of low-pass filter, particularly
    suited for smoothing noisy data. The main idea behind this
    approach is to make for each point a least-square fit with a
    polynomial of high order over a odd-sized window centered at
    the point.

    Examples
    --------
    t = np.linspace(-4, 4, 500)
    y = np.exp( -t**2 ) + np.random.normal(0, 0.05, t.shape)
    ysg = savitzky_golay(y, window_size=31, order=4)
    import matplotlib.pyplot as plt
    plt.plot(t, y, label='Noisy signal')
    plt.plot(t, np.exp(-t**2), 'k', lw=1.5, label='Original signal')
    plt.plot(t, ysg, 'r', label='Filtered signal')
    plt.legend()
    plt.show()

    References
    ----------
    .. [1] A. Savitzky, M. J. E. Golay, Smoothing and Differentiation of
       Data by Simplified Least Squares Procedures. Analytical
       Chemistry, 1964, 36 (8), pp 1627-1639.
    .. [2] Numerical Recipes 3rd Edition: The Art of Scientific Computing
       W.H. Press, S.A. Teukolsky, W.T. Vetterling, B.P. Flannery
       Cambridge University Press ISBN-13: 9780521880688
    """

    try:
        window_size = np.abs(np.int_(window_size))
        order = np.abs(np.int_(order))
    except ValueError as msg:  # pragma: no cover
        raise ValueError("window_size and order have to be of type int")

    if window_size % 2 != 1 or window_size < 1:  # pragma: no cover
        raise TypeError("window_size size must be a positive odd number")

    if window_size < order + 2:  # pragma: no cover
        raise TypeError("window_size is too small for the polynomials order")

    order_range = range(order+1)
    half_window = (window_size - 1) // 2

    # precompute coefficients
    b = np.array([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
    m = np.linalg.pinv(b)[deriv] * rate**deriv * factorial(deriv)

    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs(y[1:half_window+1][::-1] - y[0])
    lastvals = y[-1] + np.abs(y[-half_window-1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve(m[::-1], y, mode='valid')


class SignalSmoother(TrialEnhancer):
    """Adjust a signal in place for each trial, to smooth it out.

    Args:
        buffer_name:    The name of a Trial buffer with signal data to smooth.
        channel_id:     The id of a channel to work on, within the named buffer (default is the first channel).
        filter_type:    Style of smoothing, one of of:
                            "gaussian"
                            "boxcar"
                            "golay"
                        (default is "gaussian")
        gaussian_std:   standard deviation to use for filter_type "gaussian" (default is 5).
        window_size:    width in samples of filter window to use with filter_type "boxcar" or "golay" (default is 5).
        poly_order:     polynomial order to use with filter_type "golay", default is 1.
    """

    def __init__(
        self,
        buffer_name: str,
        channel_id: str | int = None,
        filter_type: str = 'gaussian',
        gaussian_std: float = 5,
        window_size: int = 5,
        poly_order: int = 1
    ) -> None:
        self.buffer_name = buffer_name
        self.channel_id = channel_id
        self.filter_type = filter_type
        self.gaussian_std = gaussian_std
        self.window_size = window_size
        self.poly_order = poly_order

        # Make the boxcar kernel so we don't have to keep making it.
        if self.filter_type.lower() == "boxcar":
            self.kernel = np.ones(self.window_size) / self.window_size
        else:
            self.kernel = None

    def enhance(
        self,
        trial: Trial,
        trial_number: int,
        experiment_info: dict[str: Any],
        subject_info: dict[str: Any]
    ) -> None:
        # Locate the named buffer in the current trial.
        signal = trial.signals.get(self.buffer_name, None)
        if signal is None:
            return

        # Locate the given or default signal channel (signals can have one or more column of data).
        if self.channel_id is None:
            channel_index = 0
        else:
            channel_index = signal.channel_ids.index(self.channel_id)

        if self.filter_type.lower() == "gaussian":
            signal.sample_data[:, channel_index] = gaussian_filter1d(
                signal.sample_data[:, channel_index],
                self.gaussian_std
            )
        elif self.filter_type.lower() == "boxcar" and signal.sample_count() >= self.window_size:
            # The argument "same" tells np.convolve() to make output the same size as the input.
            signal.sample_data[:, channel_index] = np.convolve(
                signal.sample_data[:, channel_index],
                self.kernel,
                "same"
            )
        elif self.filter_type.lower() == "golay":
            signal.sample_data[:, channel_index] = savitzky_golay(
                signal.sample_data[:, channel_index],
                self.window_size,
                self.poly_order
            )
