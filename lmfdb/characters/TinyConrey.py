from sage.all import (gcd, Mod, Integer, Integers, Rational, pari, Pari,
                      DirichletGroup, CyclotomicField, euler_phi, lcm)
from sage.misc.cachefunc import cached_method
from sage.modular.dirichlet import DirichletCharacter
from lmfdb.logger import make_logger
logger = make_logger("TinyConrey")

def symbol_numerator(cond, parity):
    # Reference: Sect. 9.3, Montgomery, Hugh L; Vaughan, Robert C. (2007).
    # Multiplicative number theory. I. Classical theory. Cambridge Studies in
    # Advanced Mathematics 97
    #
    # Let F = Q(\sqrt(d)) with d a non zero squarefree integer then a real
    # Dirichlet character \chi(n) can be represented as a Kronecker symbol
    # (m / n) where { m  = d if # d = 1 mod 4 else m = 4d if d = 2,3 (mod) 4 }
    # and m is the discriminant of F. The conductor of \chi is |m|.
    #
    # symbol_numerator returns the appropriate Kronecker symbol depending on
    # the conductor of \chi.
    m = cond
    if cond % 2 == 1:
        if cond % 4 == 3:
            m = -cond
    elif cond % 8 == 4:
        # Fixed cond % 16 == 4 and cond % 16 == 12 were switched in the
        # previous version of the code.
        #
        # Let d be a non zero squarefree integer. If d  = 2,3 (mod) 4 and if
        # cond = 4d = 4 ( 4n + 2) or 4 (4n + 3) = 16 n + 8 or 16n + 12 then we
        # set m = cond.  On the other hand if d = 1 (mod) 4 and cond = 4d = 4
        # (4n +1) = 16n + 4 then we set m = -cond.
        if cond % 16 == 4:
            m = -cond
    elif cond % 16 == 8:
        if parity == 1:
            m = -cond
    else:
        return None
    return m


def kronecker_symbol(m):
    if m:
        return r'\(\displaystyle\left(\frac{%s}{\bullet}\right)\)' % (m)
    else:
        return None

###############################################################################
# Conrey character with no call to Jonathan's code
# in order to handle big moduli


def get_sage_genvalues(modulus, order, genvalues, zeta_order):
    """
    Helper method for computing correct genvalues when constructing
    the sage character
    """
    phi_mod = euler_phi(modulus)
    exponent_factor = phi_mod / order
    genvalues_exponent = (x * exponent_factor for x in genvalues)
    return [x * zeta_order / phi_mod for x in genvalues_exponent]


class PariConreyGroup():

    def __init__(self, modulus):
        self.modulus = int(modulus)
        self.G = Pari("znstar({},1)".format(modulus))

    def gens(self):
        return Integers(self.modulus).unit_gens()

    def invariants(self):
        return pari("znstar({},1).cyc".format(self.modulus))


class ConreyCharacter():
    """
    tiny implementation on Conrey index only
    """

    def __init__(self, modulus, number):
        assert gcd(modulus, number)==1
        self.modulus = Integer(modulus)
        self.number = Integer(number)
        self.G = Pari("znstar({},1)".format(modulus))
        self.G_gens = Integers(self.modulus).unit_gens()
        self.chi_pari = pari("znconreylog(%s,%d)"%(self.G,self.number))
        self.chi_0 = None
        self.indlabel = None

    @property
    def texname(self):
        from lmfdb.characters.web_character import WebDirichlet
        return WebDirichlet.char2tex(self.modulus, self.number)

    @cached_method
    def modfactor(self):
        return self.modulus.factor()

    @cached_method
    def conductor(self):
        B = pari("znconreyconductor(%s,%s,&chi0)"%(self.G, self.chi_pari))
        if B.type() == 't_INT':
            # means chi is primitive
            self.chi_0 = self.chi_pari
            self.indlabel = self.number
            return int(B)
        else:
            self.chi_0 = pari("chi0")
            G_0 = Pari("znstar({},1)".format(B))
            self.indlabel = int(pari("znconreyexp(%s,%s)"%(G_0,self.chi_0)))
            return int(B[0])

    @cached_method
    def is_primitive(self):
        return self.conductor() == self.modulus

    @cached_method
    def parity(self):
        number = self.number
        par = 0
        for p,e in self.modfactor():
            if p == 2:
                if number % 4 == 3:
                    par = 1 - par
            else:
                phi2 = (p-1)/Integer(2) * p **(e-1)
                if Mod(number, p ** e)**phi2 != 1:
                    par = 1 - par
        return par

    def is_odd(self):
        return self.parity() == 1

    def is_even(self):
        return self.parity() == 0

    @cached_method
    def multiplicative_order(self):
        return Mod(self.number, self.modulus).multiplicative_order()

    @property
    def order(self):
        return self.multiplicative_order()

    @property
    def genvalues(self):
        # This assumes that the generators are ordered in the way
        # that Sage returns
        return [self.conreyangle(k) * self.order for k in self.G_gens]

    @property
    def values_gens(self):
        # This may be considered the full version of genvalues;
        # that is, it returns both the generators as well as the values
        # at those generators
        return [[k, self.conreyangle(k) * self.order] for k in self.G_gens]

    @cached_method
    def kronecker_symbol(self):
        c = self.conductor()
        p = self.parity()
        return kronecker_symbol(symbol_numerator(c, p))

    def conreyangle(self,x):
        return Rational(pari("chareval(%s,znconreylog(%s,%d),%d)"%(self.G,self.G,self.number,x)))

    def gauss_sum_numerical(self, a):
        # There seems to be a bug in pari when a is a multiple of the modulus,
        # so we deal with that separately
        if self.modulus.divides(a):
            if self.conductor() == 1:
                return euler_phi(self.modulus)
            else:
                return Integer(0)
        else:
            return pari("znchargauss(%s,%s,a=%d)"%(self.G,self.chi_pari,a))

    def sage_zeta_order(self, order):
        return 1 if self.modulus <= 2 else lcm(2,order)

    def sage_character(self, order=None, genvalues=None):

        if order is None:
            order = self.order

        if genvalues is None:
            genvalues = self.genvalues

        H = DirichletGroup(self.modulus, base_ring=CyclotomicField(self.sage_zeta_order(order)))
        M = H._module
        order_corrected_genvalues = get_sage_genvalues(self.modulus, order, genvalues, self.sage_zeta_order(order))
        return DirichletCharacter(H,M(order_corrected_genvalues))

    @cached_method
    def galois_orbit(self, limit=200):
        order = self.order
        if order == 1:
            return [1]
        elif order < limit or order * order < limit * self.modulus:
            logger.debug(f"compute all conjugate characters and return first {limit}")
            return self.galois_orbit_all(limit)
        elif self.modulus < 30 * order:
            logger.debug(f"compute {limit} first conjugate characters")
            return self.galois_orbit_search(limit)
        else:
            logger.debug(f"galois orbit of size {order} too expansive, give up")
            return []

    def galois_orbit_all(self, limit=200):
        # construct all Galois orbit, assume not too large
        order = self.order
        chi = chik = Mod(self.number, self.modulus)
        output = []
        for k in range(2,order):
            if gcd(k,order) == 1:
                output.append(Integer(chik))
                chik *= chi
        output.sort()
        return output[:100]

    def galois_orbit_search(self, limit=200):
        # fishing strategy, assume orbit relatively dense
        order = self.order
        num = self.number
        mod = self.modulus
        kmax = limit * 50
        cmd = f"a=Mod({num},{mod});my(valid(k)=my(l=znlog(k,a,{order}));l&&gcd(l,{order})==1);[ k | k <- [1..{kmax}], gcd(k,{mod})==1 && valid(k) ]"
        return list(map(Integer,pari(cmd)[:limit]))

    @cached_method
    def kernel_field_poly(self):
        k = pari("charker(%s,%s)"%(self.G, self.chi_pari))
        pol = pari("galoissubcyclo(%s,%s)"%(self.G, k))
        if self.order <= 12:
            pol = pari("polredabs(%s)"%(pol))
        return pol

    @property
    def min_conrey_conj(self):
        return self.galois_orbit(1)[0]
