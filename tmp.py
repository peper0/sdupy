import sdupy

from sdupy.reactive import Var, reactive

ra = sdupy.axes('a')

v = Var([Var([1, 2, 2, 1]), Var([4, 2, 0, 1])])
ind = Var(0)

xlim = ra.get_xlim()
xlim
ra.set_xlim([9, 100])


@reactive
def my_plot(vv, ind):
    res = ra.plot(vv[ind])
    return res


yy = my_plot(v, ind)
ra.grid(True, which='both')
