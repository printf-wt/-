#include "tcp_receiver.hh"

#include <algorithm>
#include <limits>
#include <utility>

using namespace std;

void TCPReceiver::receive( TCPSenderMessage message )
{
  if ( message.RST ) {
    reader().set_error();
    return;
  }
  if ( reader().has_error() ) {
    return;
  }

  if ( not isn_.has_value() ) {
    if ( not message.SYN ) {
      return;
    }
    isn_ = message.seqno;
  }

  const uint64_t absolute_seqno = message.seqno.unwrap( isn_.value(), writer().bytes_pushed() + 1 );
  if ( absolute_seqno == 0 and not message.SYN ) {
    return; // Sequence zero belongs to SYN, not to a byte of payload.
  }
  const uint64_t stream_index = absolute_seqno - ( message.SYN ? 0 : 1 );
  reassembler_.insert( stream_index, move( message.payload ), message.FIN );
}

TCPReceiverMessage TCPReceiver::send() const
{
  TCPReceiverMessage message;
  message.window_size
    = static_cast<uint16_t>( min<uint64_t>( writer().available_capacity(), numeric_limits<uint16_t>::max() ) );
  message.RST = reader().has_error();
  if ( isn_.has_value() ) {
    // SYN and the fully reassembled FIN each consume one sequence number.
    const uint64_t next_seqno = writer().bytes_pushed() + 1 + ( writer().is_closed() ? 1 : 0 );
    message.ackno = Wrap32::wrap( next_seqno, isn_.value() );
  }
  return message;
}
