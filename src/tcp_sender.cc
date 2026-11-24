#include "tcp_sender.hh"
#include "tcp_config.hh"

#include <algorithm>
#include <limits>

using namespace std;

// How many sequence numbers are outstanding?
uint64_t TCPSender::sequence_numbers_in_flight() const
{
  return next_seqno_ - acknowledged_seqno_;
}

// How many consecutive retransmissions have happened?
uint64_t TCPSender::consecutive_retransmissions() const
{
  return consecutive_retransmissions_;
}

void TCPSender::push( const TransmitFunction& transmit )
{
  while ( not fin_sent_ ) {
    // A zero window allows one probe, but its real value is kept for the timer.
    const uint64_t effective_window = max<uint64_t>( window_size_, 1 );
    if ( sequence_numbers_in_flight() >= effective_window ) {
      break;
    }
    const uint64_t space = effective_window - sequence_numbers_in_flight();
    auto message = make_empty_message();
    message.SYN = next_seqno_ == 0;
    read(
      reader(), min<uint64_t>( TCPConfig::MAX_PAYLOAD_SIZE, space - ( message.SYN ? 1 : 0 ) ), message.payload );
    message.FIN = reader().is_finished() and message.sequence_length() < space;
    const uint64_t length = message.sequence_length();
    if ( length == 0 ) {
      break;
    }

    if ( outstanding_.empty() ) {
      elapsed_ms_ = 0; // Start the timer only when the first outstanding message appears.
    }
    next_seqno_ += length;
    fin_sent_ = message.FIN;
    outstanding_.push_back( { next_seqno_, message } );
    transmit( message );
  }
}

TCPSenderMessage TCPSender::make_empty_message() const
{
  return { .seqno = Wrap32::wrap( next_seqno_, isn_ ), .RST = input_.has_error() };
}

void TCPSender::receive( const TCPReceiverMessage& msg )
{
  if ( msg.RST ) {
    writer().set_error();
    return;
  }
  const uint64_t ackno = msg.ackno.has_value() ? msg.ackno->unwrap( isn_, next_seqno_ ) : acknowledged_seqno_;
  if ( ackno > next_seqno_ ) {
    return; // An acknowledgment cannot cover sequence numbers that have not been sent.
  }
  window_size_ = msg.window_size;
  if ( ackno <= acknowledged_seqno_ ) {
    return;
  }

  acknowledged_seqno_ = ackno;
  while ( not outstanding_.empty() and outstanding_.front().end_seqno <= ackno ) {
    outstanding_.pop_front();
  }
  // Partly acknowledged messages remain intact for retransmission.
  RTO_ms_ = initial_RTO_ms_;
  elapsed_ms_ = 0;
  consecutive_retransmissions_ = 0;
}

void TCPSender::tick( uint64_t ms_since_last_tick, const TransmitFunction& transmit )
{
  if ( outstanding_.empty() ) {
    return; // An empty outstanding queue also means that the timer is stopped.
  }
  if ( ms_since_last_tick < RTO_ms_ - elapsed_ms_ ) {
    elapsed_ms_ += ms_since_last_tick;
    return;
  }

  auto message = outstanding_.front().message;
  message.RST = input_.has_error();
  elapsed_ms_ = 0;
  if ( window_size_ != 0 ) {
    ++consecutive_retransmissions_;
    const uint64_t maximum = numeric_limits<uint64_t>::max();
    RTO_ms_ = RTO_ms_ > maximum / 2 ? maximum : RTO_ms_ * 2;
  }
  transmit( message );
}
