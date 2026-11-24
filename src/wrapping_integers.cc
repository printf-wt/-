#include "wrapping_integers.hh"

#include <limits>

using namespace std;

Wrap32 Wrap32::wrap( uint64_t n, Wrap32 zero_point )
{
  return zero_point + static_cast<uint32_t>( n );
}

uint64_t Wrap32::unwrap( Wrap32 zero_point, uint64_t checkpoint ) const
{
  constexpr uint64_t modulus = uint64_t { 1 } << 32;
  const uint64_t offset = static_cast<uint32_t>( raw_value_ - zero_point.raw_value_ );
  uint64_t candidate = ( checkpoint & ~( modulus - 1 ) ) | offset;
  const auto distance
    = [checkpoint]( uint64_t value ) { return value > checkpoint ? value - checkpoint : checkpoint - value; };

  // Inspect neighboring cycles without underflowing or overflowing uint64_t.
  if ( candidate >= modulus and distance( candidate - modulus ) <= distance( candidate ) ) {
    candidate -= modulus;
  }
  if ( candidate <= numeric_limits<uint64_t>::max() - modulus
       and distance( candidate + modulus ) < distance( candidate ) ) {
    candidate += modulus;
  }
  return candidate;
}
