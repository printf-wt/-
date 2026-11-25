"""Run extra Wrap32 uint64 boundary checks in Ubuntu without changing official tests."""

from pathlib import Path
import subprocess
import tempfile


SOURCE = r'''
#include "wrapping_integers.hh"

#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

int main()
{
  try {
    constexpr uint64_t modulus = uint64_t { 1 } << 32;
    constexpr uint64_t maximum = std::numeric_limits<uint64_t>::max();
    constexpr uint32_t raw_maximum = std::numeric_limits<uint32_t>::max();
    constexpr uint64_t last_cycle = maximum - raw_maximum;
    unsigned int passed = 0;
    const auto check = [&passed]( bool condition, std::string_view label ) {
      if ( not condition ) {
        throw std::runtime_error( std::string( label ) );
      }
      ++passed;
    };

    check( Wrap32::wrap( maximum, Wrap32 { 1 } ) == Wrap32 { 0 }, "wrap UINT64_MAX with ISN=1" );
    check( Wrap32 { raw_maximum }.unwrap( Wrap32 { 0 }, maximum ) == maximum, "unwrap exact UINT64_MAX" );
    check( Wrap32 { 0 }.unwrap( Wrap32 { 0 }, maximum ) == last_cycle, "last representable cycle" );
    check( Wrap32 { 0 }.unwrap( Wrap32 { raw_maximum }, maximum ) == last_cycle + 1,
           "nonzero ISN near UINT64_MAX" );
    check( Wrap32 { raw_maximum }.unwrap( Wrap32 { 0 }, 0 ) == raw_maximum,
           "negative absolute candidate must be excluded" );
    check( Wrap32 { 0 }.unwrap( Wrap32 { 0 }, modulus / 2 ) == 0, "lower candidate on a tie" );
    check( Wrap32 { 0 }.unwrap( Wrap32 { 0 }, last_cycle + modulus / 2 ) == last_cycle,
           "candidate above UINT64_MAX must be excluded" );
    check( Wrap32 { raw_maximum }.unwrap( Wrap32 { 0 }, maximum - modulus / 2 ) == maximum - modulus,
           "lower tie near uint64 upper boundary" );
    check( Wrap32 { 17 }.unwrap( Wrap32 { 18 }, maximum ) == maximum,
           "nonzero ISN exact uint64 upper boundary" );
    check( Wrap32::wrap( modulus, Wrap32 { 57 } ) == Wrap32 { 57 }, "one whole sequence cycle" );

    std::cout << passed << " supplementary Wrap32 boundary checks passed with ASan/UBSan.\n";
  } catch ( const std::exception& error ) {
    std::cerr << "Boundary check failed: " << error.what() << '\n';
    return 1;
  }
  return 0;
}
'''


def main():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="check2-boundary-") as directory:
        scratch = Path(directory)
        source = scratch / "boundaries.cc"
        binary = scratch / "boundaries"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run(
            [
                "g++", "-std=c++23", "-O1", "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all", "-I", str(root / "src"),
                str(source), str(root / "src/wrapping_integers.cc"),
                "-o", str(binary),
            ],
            check=True,
        )
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
