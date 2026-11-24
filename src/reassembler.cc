#include "reassembler.hh"

#include <algorithm>
#include <iterator>
#include <limits>

using namespace std;

void Reassembler::insert( uint64_t first_index, string data, bool is_last_substring )
{
  auto& output = output_.writer();
  if ( output.is_closed() ) {
    return;
  }

  const uint64_t max_index = numeric_limits<uint64_t>::max();
  if ( is_last_substring and data.size() <= max_index - first_index ) {
    end_index_ = first_index + data.size();
  }

  // Unread output and pending bytes share one capacity-limited index window.
  const uint64_t next_index = output.bytes_pushed();
  const uint64_t window_end = next_index + min( output.available_capacity(), max_index - next_index );
  const uint64_t first = max( first_index, next_index );
  uint64_t last = min( window_end, end_index_.value_or( window_end ) );

  if ( first < last and first - first_index < data.size() ) {
    last = first + min<uint64_t>( data.size() - ( first - first_index ), last - first );
    auto next = pending_.lower_bound( first );
    uint64_t cursor = first;
    if ( next != pending_.begin() ) {
      const auto previous = prev( next );
      cursor = max<uint64_t>( cursor, previous->first + previous->second.size() );
    }

    // Store only gaps between existing ranges, preserving just one copy per byte.
    while ( cursor < last ) {
      if ( next == pending_.end() or next->first >= last ) {
        const bool whole_substring = cursor == first_index and last - cursor == data.size();
        pending_.emplace_hint(
          next, cursor, whole_substring ? move( data ) : data.substr( cursor - first_index, last - cursor ) );
        break;
      }
      if ( cursor < next->first ) {
        pending_.emplace_hint( next, cursor, data.substr( cursor - first_index, next->first - cursor ) );
      }
      cursor = max<uint64_t>( cursor, next->first + next->second.size() );
      ++next;
    }
  }

  // Deliver every contiguous range immediately; leave later ranges behind a gap.
  while ( not pending_.empty() and pending_.begin()->first == output.bytes_pushed() ) {
    output.push( move( pending_.begin()->second ) );
    pending_.erase( pending_.begin() );
  }
  if ( end_index_.has_value() and output.bytes_pushed() == end_index_.value() ) {
    output.close();
  }
}

// How many bytes are stored in the Reassembler itself?
// This function is for testing only; don't add extra state to support it.
uint64_t Reassembler::count_bytes_pending() const
{
  uint64_t total = 0;
  for ( const auto& [index, bytes] : pending_ ) {
    total += bytes.size();
  }
  return total;
}
