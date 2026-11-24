#include "byte_stream.hh"

#include <algorithm>
#include <utility>

using namespace std;

ByteStream::ByteStream( uint64_t capacity ) : capacity_( capacity ) {}

// Push data to stream, but only as much as available capacity allows.
void Writer::push( string data )
{
  if ( closed_ ) {
    return;
  }

  const uint64_t length = min<uint64_t>( data.size(), available_capacity() );
  if ( length == 0 ) {
    return;
  }

  if ( length < data.size() ) {
    data = data.substr( 0, length );
  }
  buffer_.push_back( move( data ) );
  bytes_pushed_ += length;
}

// Signal that the stream has reached its ending. Nothing more will be written.
void Writer::close()
{
  closed_ = true;
}

// Has the stream been closed?
bool Writer::is_closed() const
{
  return closed_;
}

// How many bytes can be pushed to the stream right now?
uint64_t Writer::available_capacity() const
{
  return capacity_ - ( bytes_pushed_ - bytes_popped_ );
}

// Total number of bytes cumulatively pushed to the stream
uint64_t Writer::bytes_pushed() const
{
  return bytes_pushed_;
}

// Peek at the next bytes in the buffer -- ideally as many as possible.
// It's not required to return a string_view of the *whole* buffer, but
// if the peeked string_view is only one byte at a time, it will probably force
// the caller to do a lot of extra work.
string_view Reader::peek() const
{
  if ( buffer_.empty() ) {
    return {};
  }
  return string_view { buffer_.front() }.substr( front_offset_ );
}

// Remove `len` bytes from the buffer.
void Reader::pop( uint64_t len )
{
  len = min( len, bytes_buffered() );
  while ( len > 0 ) {
    const uint64_t length = min<uint64_t>( len, buffer_.front().size() - front_offset_ );
    front_offset_ += length;
    bytes_popped_ += length;
    len -= length;

    // Retire complete chunks without copying the unread bytes after each pop.
    if ( front_offset_ == buffer_.front().size() ) {
      buffer_.pop_front();
      front_offset_ = 0;
    }
  }
}

// Is the stream finished (closed and fully popped)?
bool Reader::is_finished() const
{
  return closed_ and bytes_buffered() == 0;
}

// Number of bytes currently buffered (pushed and not popped)
uint64_t Reader::bytes_buffered() const
{
  return bytes_pushed_ - bytes_popped_;
}

// Total number of bytes cumulatively popped from stream
uint64_t Reader::bytes_popped() const
{
  return bytes_popped_;
}
